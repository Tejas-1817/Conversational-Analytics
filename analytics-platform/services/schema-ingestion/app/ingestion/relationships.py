"""Stage 3 — Relationship detection (candidates, never auto-approved except declared FKs).

Confidence-ordered detectors:
1. declared_fk   — handled in introspector (database facts, approved, confidence 1.0)
2. naming        — order.customer_id -> customers.id style conventions
3. value_overlap — sampled inclusion test, only run on naming candidates (bounds cost)
4. llm           — stub; wire an AI provider and keep output as draft candidates

Every candidate stores its evidence so reviewers can see WHY before approving.
"""
import json
import uuid

import structlog
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.llm.orchestrator import ai_orchestrator
from app.models import ColumnMeta, DataSource, Relationship, TableMeta

log = structlog.get_logger()


def run_relationship_detection(session: Session, source: DataSource, engine: Engine) -> dict:
    stats = {"naming_candidates": 0, "overlap_confirmed": 0, "overlap_rejected": 0, "llm_candidates": 0}

    tables = session.query(TableMeta).filter_by(source_id=source.id, is_active=True).all()
    by_name = {t.table_name.lower(): t for t in tables}

    pk_by_table: dict[str, ColumnMeta] = {}
    for t in tables:
        pks = [c for c in t.columns if c.is_primary_key and c.is_active]
        if len(pks) == 1:  # composite keys: out of scope for naming heuristic
            pk_by_table[t.table_name.lower()] = pks[0]

    existing = {(r.from_column_id, r.to_column_id)
                for r in session.query(Relationship.from_column_id, Relationship.to_column_id)}

    for t in tables:
        for col in (c for c in t.columns if c.is_active and not c.is_primary_key):
            target = _match_by_naming(col.column_name, by_name, pk_by_table)
            if target is None:
                continue
            target_table, target_pk = target
            if (col.id, target_pk.id) in existing or t.id == target_table.id:
                continue
            stats["naming_candidates"] += 1

            confidence, evidence = _score_by_value_overlap(engine, t, col, target_table, target_pk)
            if confidence is None:
                continue  # overlap check errored; skip rather than guess
            if confidence < get_settings().overlap_min_confidence:
                stats["overlap_rejected"] += 1
                log.info("candidate_below_threshold", from_=f"{t.table_name}.{col.column_name}",
                         to=f"{target_table.table_name}.{target_pk.column_name}", confidence=confidence)
                continue

            session.add(Relationship(
                from_column_id=col.id, to_column_id=target_pk.id,
                cardinality="many_to_one", source="value_overlap",
                confidence=round(confidence, 3), evidence=evidence, status="draft",
            ))
            existing.add((col.id, target_pk.id))
            stats["overlap_confirmed"] += 1

    stats["llm_candidates"] = _llm_suggestions(session, tables, existing, engine)
    session.flush()
    return stats


def _match_by_naming(column_name: str, tables_by_name: dict, pk_by_table: dict):
    """customer_id -> table 'customers' or 'customer' with a single-column PK."""
    lowered = column_name.lower()
    if not lowered.endswith("_id") or lowered == "id":
        return None
    stem = lowered[:-3]  # strip _id
    for candidate in (stem, stem + "s", stem + "es", stem[:-1] + "ies" if stem.endswith("y") else None):
        if candidate and candidate in tables_by_name and candidate in pk_by_table:
            return tables_by_name[candidate], pk_by_table[candidate]
    return None


def _score_by_value_overlap(engine: Engine, from_table, from_col, to_table, to_col):
    """Sampled inclusion test: what fraction of child values exist in the parent key?"""
    settings = get_settings()
    q = engine.dialect.identifier_preparer.quote
    child = f"{q(from_table.schema_name)}.{q(from_table.table_name)}"
    parent = f"{q(to_table.schema_name)}.{q(to_table.table_name)}"
    overlap_sql = f"""
        SELECT count(*) AS total,
               count(p.pk) AS matched
        FROM (SELECT DISTINCT {q(from_col.column_name)} AS v FROM {child}
              WHERE {q(from_col.column_name)} IS NOT NULL
              LIMIT {settings.overlap_sample_values}) c
        LEFT JOIN (SELECT {q(to_col.column_name)} AS pk FROM {parent}) p ON p.pk = c.v
    """  # noqa: S608 — identifiers quoted via identifier_preparer, limit is a config int
    try:
        with engine.connect() as conn:
            result = conn.execute(text(overlap_sql)).one()
        total, matched = int(result[0]), int(result[1])
        if total == 0:
            return None, {}
        ratio = matched / total
        return ratio, {"rule": "naming+value_overlap", "sampled_distinct_values": total,
                       "matched_in_parent": matched, "overlap_ratio": round(ratio, 4)}
    except Exception as exc:
        log.warning("overlap_check_failed", from_=f"{from_table.table_name}.{from_col.column_name}",
                    to=f"{to_table.table_name}.{to_col.column_name}", error=str(exc))
        return None, {}


class LLMRelationshipCandidate(BaseModel):
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    confidence: float = Field(ge=0, le=1)
    evidence_reasoning: str

class LLMRelationshipResponse(BaseModel):
    candidates: list[LLMRelationshipCandidate]


def _llm_suggestions(session: Session, tables: list[TableMeta], existing: set[tuple[uuid.UUID, uuid.UUID]], engine: Engine) -> int:
    # 1. Gather context
    table_context = []
    col_by_name = {} # Map "table.col" -> col.id
    pk_by_table = {}

    for t in tables:
        cols = []
        for c in t.columns:
            if not c.is_active:
                continue
            key = f"{t.table_name}.{c.column_name}".lower()
            col_by_name[key] = c
            if c.is_primary_key:
                pk_by_table[t.table_name.lower()] = c

            # Safe samples
            samples = c.profile.get("sample_values", []) if c.profile else []
            cols.append({
                "name": c.column_name,
                "type": c.data_type,
                "is_pk": c.is_primary_key,
                "samples": samples[:3] # Just a few samples
            })
        table_context.append({"table": t.table_name, "columns": cols})

    if not table_context:
        return 0

    prompt = (
        "You are an expert data architect analyzing a database schema. "
        "Based on the following tables, columns, and sample values, suggest potential foreign key relationships "
        "that are not explicitly declared. Focus on semantic matches where one column acts as a reference to another table's primary key.\n\n"
        f"Schema Context:\n{json.dumps(table_context, indent=2)}\n\n"
        "Return a list of candidates. Be conservative. Provide reasoning for each."
    )

    try:
        response = ai_orchestrator.generate_structured(prompt, LLMRelationshipResponse)
    except Exception as e:
        log.error("llm_relationship_detection_failed", error=str(e))
        return 0

    added = 0
    for cand in response.candidates:
        from_key = f"{cand.from_table}.{cand.from_column}".lower()
        to_key = f"{cand.to_table}.{cand.to_column}".lower()

        from_col = col_by_name.get(from_key)
        to_col = col_by_name.get(to_key)

        if not from_col or not to_col:
            continue

        # Ensure 'to' is a primary key, or at least a different table
        if from_col.table_id == to_col.table_id:
            continue

        if (from_col.id, to_col.id) in existing:
            continue

        session.add(Relationship(
            from_column_id=from_col.id, to_column_id=to_col.id,
            cardinality="many_to_one", source="llm",
            confidence=round(min(cand.confidence, 0.7), 3), # Modest confidence
            evidence={"reasoning": cand.evidence_reasoning}, status="draft",
        ))
        existing.add((from_col.id, to_col.id))
        added += 1

    return added

