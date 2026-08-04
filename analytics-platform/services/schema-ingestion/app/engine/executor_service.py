"""Executor Service.

Executes compiled Text-to-SQL queries against the customer's actual target DataSource
using read-only connector engines. Ensures engines are disposed after query execution.
"""
import time
from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional
import structlog
from sqlalchemy import text

from app.connectors.factory import build_engine
from app.engine.compiler_service import CompiledQuery
from app.models import DataSource

log = structlog.get_logger(__name__)


class ExecutorResult:
    def __init__(self, columns: list, rows: list, execution_time_ms: int):
        self.columns = columns
        self.rows = rows
        self.execution_time_ms = execution_time_ms


class ExecutorService:
    @staticmethod
    def execute(source: DataSource, compiled: CompiledQuery) -> ExecutorResult:
        """Executes compiled SQL query on customer's actual target DataSource using short-lived read-only engine."""
        start_time = time.time()
        engine = None
        try:
            log.info("connecting_to_target_datasource", source_id=str(source.id), source_name=source.name)
            engine = build_engine(source)
            
            with engine.connect() as conn:
                stmt = text(compiled.sql)
                result = conn.execute(stmt, compiled.params or {})
                columns = list(result.keys())

                def _serialize(val: Any) -> Any:
                    if isinstance(val, Decimal):
                        return float(val)
                    if isinstance(val, datetime):
                        return val.isoformat()
                    return val

                rows = []
                for row in result.fetchall():
                    rows.append({k: _serialize(v) for k, v in row._mapping.items()})

                execution_time_ms = int((time.time() - start_time) * 1000)
                log.info("customer_query_executed", source=source.name, row_count=len(rows), time_ms=execution_time_ms)
                return ExecutorResult(columns, rows, execution_time_ms)
        finally:
            if engine is not None:
                try:
                    engine.dispose()
                    log.info("target_datasource_engine_disposed", source_id=str(source.id))
                except Exception as e:
                    log.warning("engine_dispose_error", error=str(e))
