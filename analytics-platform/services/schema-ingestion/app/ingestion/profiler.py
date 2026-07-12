"""Stage 2 — Data profiling.

Per-column statistics computed over a bounded sample, with guardrails in code:
sampling limits, per-query timeouts (set at connection level), PII masking.
A profiling failure on one table never aborts the whole run.
"""
import structlog
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.ingestion.pii import mask_samples
from app.models import DataSource, TableMeta

log = structlog.get_logger()

_ORDERABLE_HINTS = ("int", "numeric", "decimal", "float", "double", "date", "time")


def _quote(engine: Engine, identifier: str) -> str:
    return engine.dialect.identifier_preparer.quote(identifier)


def run_profiling(session: Session, source: DataSource, engine: Engine) -> dict:
    settings = get_settings()
    stats = {"tables_profiled": 0, "columns_profiled": 0, "errors": 0}

    tables = session.query(TableMeta).filter_by(source_id=source.id, is_active=True).all()
    for table in tables:
        fq_table = f"{_quote(engine, table.schema_name)}.{_quote(engine, table.table_name)}"
        try:
            with engine.connect() as conn:
                row_count = conn.execute(text(f"SELECT count(*) FROM {fq_table}")).scalar_one()  # noqa: S608 — identifiers quoted via identifier_preparer, limits are config ints
                table.row_count = int(row_count)

                for column in (c for c in table.columns if c.is_active):
                    col = _quote(engine, column.column_name)
                    sample = f"(SELECT {col} AS v FROM {fq_table} LIMIT {settings.profile_sample_rows}) s"  # noqa: S608 — identifiers quoted, limit is config int

                    base = conn.execute(text(
                        f"SELECT count(*), count(v), count(DISTINCT v) FROM {sample}"  # noqa: S608 — identifiers quoted via identifier_preparer, limits are config ints
                    )).one()
                    sampled, non_null, distinct = int(base[0]), int(base[1]), int(base[2])

                    profile: dict = {
                        "sampled_rows": sampled,
                        "null_rate": round(1 - (non_null / sampled), 4) if sampled else None,
                        "distinct_count_sampled": distinct,
                    }

                    if any(h in column.data_type.lower() for h in _ORDERABLE_HINTS):
                        mn, mx = conn.execute(text(f"SELECT min(v), max(v) FROM {sample}")).one()  # noqa: S608 — identifiers quoted via identifier_preparer, limits are config ints
                        profile["min"], profile["max"] = str(mn), str(mx)

                    top = conn.execute(text(
                        f"SELECT v, count(*) AS c FROM {sample} WHERE v IS NOT NULL "  # noqa: S608 — identifiers quoted via identifier_preparer, limits are config ints
                        f"GROUP BY v ORDER BY c DESC LIMIT {settings.profile_top_n_values}"
                    )).all()
                    profile["sample_values"] = mask_samples(column.column_name, [r[0] for r in top])

                    column.profile = profile
                    stats["columns_profiled"] += 1

            stats["tables_profiled"] += 1
        except Exception as exc:  # one bad table must not sink the run
            stats["errors"] += 1
            log.warning("profiling_failed", table=f"{table.schema_name}.{table.table_name}", error=str(exc))

    session.flush()
    return stats
