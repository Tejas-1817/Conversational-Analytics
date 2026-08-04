"""SQL Executor.

Executes validated read-only SELECT queries against the connected customer DataSource
safely with statement timeouts, row limits, and connection verification logging.
"""
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import uuid
import structlog
from sqlalchemy import text

from app.connectors.factory import build_engine
from app.db import get_engine
from app.models import DataSource

log = structlog.get_logger(__name__)


class SQLExecutor:
    """Safely executes read-only SQL queries on the active customer database."""

    @staticmethod
    def execute_query(
        sql: str,
        source: Optional[DataSource] = None,
        limit: int = 100,
        timeout_ms: int = 5000
    ) -> Tuple[List[Dict[str, Any]], int, float, List[str]]:
        """Executes a read-only SELECT query and returns (result_data, row_count, execution_time_ms, columns)."""
        if not sql or "UNANSWERABLE" in sql.upper() or not sql.strip().upper().startswith(("SELECT", "WITH")):
            return [], 0, 0.0, []

        start_time = time.time()
        engine = None
        should_dispose = False

        if source is not None:
            try:
                engine = build_engine(source)
                should_dispose = True
            except Exception as exc:
                log.error("failed_to_build_datasource_engine", source_id=str(source.id), error=str(exc))
                engine = get_engine()
        else:
            engine = get_engine()

        try:
            with engine.connect() as conn:
                # 1. Connection Verification & Logging
                curr_db = "unknown"
                curr_schema = "unknown"
                try:
                    curr_db = conn.execute(text("SELECT current_database()")).scalar() or "unknown"
                    curr_schema = conn.execute(text("SELECT current_schema()")).scalar() or "unknown"
                except Exception as ver_exc:
                    log.warning("connection_verification_failed", error=str(ver_exc))

                log.info(
                    "sql_execution_connection_verified",
                    tenant_id=str(source.tenant_id) if source else "system",
                    source_id=str(source.id) if source else "default",
                    database_name=curr_db,
                    schema_name=curr_schema,
                    source_name=source.name if source else "default"
                )

                # 2. Enforce statement timeout and execute query
                conn.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))
                res = conn.execute(text(sql))
                keys = list(res.keys())
                rows = res.fetchmany(limit)

                # 3. Type Serialization
                def _serialize_val(v: Any) -> Any:
                    if v is None:
                        return None
                    if isinstance(v, Decimal):
                        return float(v) if v % 1 != 0 else int(v)
                    if isinstance(v, (datetime, date)):
                        return v.isoformat()
                    if isinstance(v, uuid.UUID):
                        return str(v)
                    if isinstance(v, (int, float, str, bool)):
                        return v
                    return str(v)

                result_data = []
                for row in rows:
                    row_dict = {}
                    for col, val in zip(keys, row):
                        row_dict[col] = _serialize_val(val)
                    result_data.append(row_dict)

                exec_time_ms = round((time.time() - start_time) * 1000, 2)

                # 4. Detailed Stage Validation Logging
                log.info(
                    "sql_execution_stage_validation",
                    generated_sql=sql,
                    rows_returned=len(result_data),
                    column_names=keys,
                    serialized_sample=result_data[:2],
                    execution_time_ms=exec_time_ms,
                    connected_db=curr_db
                )

                return result_data, len(result_data), exec_time_ms, keys
        except Exception as exc:
            exec_time_ms = round((time.time() - start_time) * 1000, 2)
            log.error(
                "sql_execution_failed_exception",
                generated_sql=sql,
                error_type=type(exc).__name__,
                error_message=str(exc),
                execution_time_ms=exec_time_ms,
                exc_info=True
            )
            return [], 0, exec_time_ms, []
        finally:
            if should_dispose and engine is not None:
                try:
                    engine.dispose()
                except Exception:
                    pass

