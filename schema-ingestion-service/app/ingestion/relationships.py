"""Stage 3 — Relationship detection (candidates, never auto-approved except declared FKs).

Confidence-ordered detectors:
1. declared_fk   — handled in introspector (database facts, approved, confidence 1.0)
2. naming        — order.customer_id -> customers.id style conventions
3. value_overlap — sampled inclusion test, only run on naming candidates (bounds cost)
4. llm           — stub; wire an AI provider and keep output as draft candidates

Every candidate stores its evidence so reviewers can see WHY before approving.
"""
import structlog
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config import get_settings
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

    stats["llm_candidates"] = _llm_suggestions_stub()
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
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"""
                SELECT count(*) AS total,
                       count(p.pk) AS matched
                FROM (SELECT DISTINCT {q(from_col.column_name)} AS v FROM {child}
                      WHERE {q(from_col.column_name)} IS NOT NULL
                      LIMIT {settings.overlap_sample_values}) c
                LEFT JOIN (SELECT {q(to_col.column_name)} AS pk FROM {parent}) p ON p.pk = c.v
            """)).one()
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


def _llm_suggestions_stub() -> int:
    """TODO(team): wire an AI provider to suggest relationships the heuristics missed.

    Contract when implemented:
    - Input: table/column names + PII-masked sample values only.
    - Output: Relationship rows with source='llm', modest confidence (<=0.7), status='draft'.
    - Never auto-approve; reviewers see evidence explaining the suggestion.
    """
    log.info("llm_relationship_detection_not_implemented")
    return 0
