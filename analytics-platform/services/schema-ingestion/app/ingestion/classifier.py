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

    _llm_enrichment_stub()
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


def _llm_enrichment_stub() -> None:
    """TODO(team): AI pass that drafts business_name, description, and synonyms per table/column.

    Contract when implemented:
    - Input: schema names, data types, PII-masked sample values, DB comments. Never raw samples.
    - Output: drafts only (status stays 'draft'); never overwrite human-edited fields
      (check updated_by != 'system').
    - Rule for reviewers: any description containing a business rule (tax, discounts,
      cancellations, currency) requires domain-owner confirmation before approval.
    """
    log.info("llm_enrichment_not_implemented")
