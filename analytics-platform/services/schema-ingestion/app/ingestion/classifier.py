"""Stage 4 — Dimension/measure classification.

Heuristics pass (implemented) + AI enrichment pass (stub). Everything lands as
status='draft'; only columns still classified by 'system' are re-touched on
re-runs, so human edits are never overwritten.

Additivity matters (top source of wrong numbers later):
- additive:      order amounts — safe to SUM
- semi_additive: balances/inventory levels — cannot SUM across time
- non_additive:  ratios/percentages — must be recomputed, never averaged
"""
import structlog
from sqlalchemy.orm import Session

from app.models import DataSource, TableMeta
from app.llm.provider import get_llm_provider
from pydantic import BaseModel, Field
import json

log = structlog.get_logger()

_MEASURE_NAME_HINTS = ("amount", "amt", "total", "price", "cost", "revenue", "qty",
                       "quantity", "count", "value", "sales", "fee", "charge")
_SEMI_ADDITIVE_HINTS = ("balance", "inventory", "stock", "on_hand", "headcount", "level")
_NON_ADDITIVE_HINTS = ("rate", "ratio", "pct", "percent", "percentage", "avg", "average", "margin")
_NUMERIC_HINTS = ("int", "numeric", "decimal", "float", "double", "money", "real")
_TEMPORAL_HINTS = ("date", "time", "timestamp")
_LOW_CARDINALITY_THRESHOLD = 50


def run_classification(session: Session, source: DataSource) -> dict:
    stats = {"classified": 0, "skipped_human_touched": 0}

    tables = session.query(TableMeta).filter_by(source_id=source.id, is_active=True).all()
    for table in tables:
        for column in (c for c in table.columns if c.is_active):
            if column.updated_by != "system" or column.status != "draft":
                stats["skipped_human_touched"] += 1
                continue
            role, aggregation, additivity = _classify(column)
            column.role, column.aggregation, column.additivity = role, aggregation, additivity
            stats["classified"] += 1

    _llm_enrichment(session, tables)
    session.flush()
    return stats


def _name_matches(name: str, hints: tuple[str, ...]) -> bool:
    """Token-based hint matching. Substring matching is too greedy:
    'account_balance' must not match the 'count' hint, 'discount_pct' must not
    match 'count' either. A hint matches only as a whole underscore-token."""
    tokens = set(name.split("_"))
    # Multi-token hints like 'on_hand' can't match a single token; check those as substrings.
    return any((h in name) if "_" in h else (h in tokens) for h in hints)


def _classify(column) -> tuple[str, str | None, str]:
    name = column.column_name.lower()
    dtype = column.data_type.lower()
    distinct = (column.profile or {}).get("distinct_count_sampled")

    if column.is_primary_key or name.endswith("_id") or name == "id":
        return "key", None, "not_applicable"
    if any(h in dtype for h in _TEMPORAL_HINTS):
        return "dimension", None, "not_applicable"
    if dtype.startswith("bool"):
        return "dimension", None, "not_applicable"

    if any(h in dtype for h in _NUMERIC_HINTS):
        if _name_matches(name, _NON_ADDITIVE_HINTS):
            return "measure", "avg", "non_additive"
        if _name_matches(name, _MEASURE_NAME_HINTS):
            return "measure", "sum", "additive"
        # Low-cardinality numerics (status codes, priority levels) are dimensions.
        # Checked BEFORE semi-additive hints: 'priority_level' must not match the
        # 'level' hint meant for 'inventory_level'-style balances.
        if distinct is not None and distinct <= _LOW_CARDINALITY_THRESHOLD:
            return "dimension", None, "not_applicable"
        if _name_matches(name, _SEMI_ADDITIVE_HINTS):
            return "measure", "sum", "semi_additive"
        return "measure", "sum", "additive"

    # strings: low-cardinality -> dimension, otherwise free-text attribute
    if distinct is not None and distinct <= _LOW_CARDINALITY_THRESHOLD:
        return "dimension", None, "not_applicable"
    return "attribute", None, "not_applicable"


class LLMColumnEnrichment(BaseModel):
    column_name: str
    business_name: str | None = None
    description: str | None = None
    synonyms: list[str] = Field(default_factory=list)

class LLMTableEnrichment(BaseModel):
    table_name: str
    business_name: str | None = None
    description: str | None = None
    columns: list[LLMColumnEnrichment]

class LLMEnrichmentResponse(BaseModel):
    tables: list[LLMTableEnrichment]

def _llm_enrichment(session: Session, tables: list[TableMeta]) -> None:
    table_context = []
    
    for t in tables:
        cols = []
        for c in t.columns:
            if not c.is_active:
                continue
            samples = c.profile.get("sample_values", []) if c.profile else []
            cols.append({
                "name": c.column_name,
                "type": c.data_type,
                "role": c.role,
                "samples": samples[:3]
            })
        table_context.append({"table": t.table_name, "columns": cols})

    if not table_context:
        return

    prompt = (
        "You are an expert data analyst. Based on the following database schema (tables, columns, types, and sample values), "
        "provide a drafted business name, description, and list of synonyms for each table and column.\n"
        "Ensure descriptions explain the business context. If you deduce any business rules (e.g., currency, tax, discounts), include them.\n\n"
        f"Schema Context:\n{json.dumps(table_context, indent=2)}\n\n"
        "Return the enrichment data."
    )

    provider = get_llm_provider()
    try:
        response = provider.generate_structured(prompt, LLMEnrichmentResponse)
    except Exception as e:
        log.error("llm_enrichment_failed", error=str(e))
        return

    # Apply drafts without overwriting human edits
    by_name = {t.table_name.lower(): t for t in tables}
    for tbl_resp in response.tables:
        t = by_name.get(tbl_resp.table_name.lower())
        if not t:
            continue
            
        if t.updated_by == "system" and t.status == "draft":
            if tbl_resp.business_name: t.business_name = tbl_resp.business_name
            if tbl_resp.description: t.description = tbl_resp.description
            
        col_by_name = {c.column_name.lower(): c for c in t.columns}
        for col_resp in tbl_resp.columns:
            c = col_by_name.get(col_resp.column_name.lower())
            if not c:
                continue
                
            if c.updated_by == "system" and c.status == "draft":
                if col_resp.business_name: c.business_name = col_resp.business_name
                if col_resp.description: c.description = col_resp.description
                if col_resp.synonyms: c.synonyms = col_resp.synonyms

