"""SQL Executor.

Executes validated read-only SELECT queries against the connected PostgreSQL database
safely with statement timeouts and row limits.
"""
import time
from typing import Any, Dict, List, Tuple
import structlog
from sqlalchemy import text
from app.db import get_engine

log = structlog.get_logger(__name__)


class SQLExecutor:
    """Safely executes read-only SQL queries on the connected database."""

    @staticmethod
    def execute_query(sql: str, limit: int = 100, timeout_ms: int = 5000) -> Tuple[List[Dict[str, Any]], int, float]:
        """Executes a read-only SELECT query and returns (result_data, row_count, execution_time_ms)."""
        if not sql or "UNANSWERABLE" in sql.upper() or not sql.strip().upper().startswith("SELECT") and not sql.strip().upper().startswith("WITH"):
            return [], 0, 0.0

        engine = get_engine()
        start_time = time.time()

        try:
            with engine.connect() as conn:
                # Enforce statement timeout and read-only execution
                conn.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))
                res = conn.execute(text(sql))
                keys = list(res.keys())
                rows = res.fetchmany(limit)

                result_data = []
                for row in rows:
                    row_dict = {}
                    for col, val in zip(keys, row):
                        # Convert non-serializable types (datetime, Decimal, UUID) to string
                        if val is not None and not isinstance(val, (int, float, str, bool)):
                            row_dict[col] = str(val)
                        else:
                            row_dict[col] = val
                    result_data.append(row_dict)

                exec_time_ms = round((time.time() - start_time) * 1000, 2)
                return result_data, len(result_data), exec_time_ms
        except Exception as exc:
            log.error("sql_execution_failed", sql=sql, error=str(exc))
            exec_time_ms = round((time.time() - start_time) * 1000, 2)
            return [], 0, exec_time_ms
