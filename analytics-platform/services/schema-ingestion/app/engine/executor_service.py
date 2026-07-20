import time

from sqlalchemy import text
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import datetime

from app.engine.compiler_service import CompiledQuery


class ExecutorResult:
    def __init__(self, columns: list, rows: list, execution_time_ms: int):
        self.columns = columns
        self.rows = rows
        self.execution_time_ms = execution_time_ms

class ExecutorService:
    @staticmethod
    def execute(db: Session, compiled: CompiledQuery) -> ExecutorResult:
        start_time = time.time()

        # Execute parameterized SQL
        stmt = text(compiled.sql)
        result = db.execute(stmt, compiled.params)

        # Fetch data
        columns = list(result.keys())
        
        def _serialize(val):
            if isinstance(val, Decimal):
                return float(val)
            if isinstance(val, datetime):
                return val.isoformat()
            return val

        rows = []
        for row in result.fetchall():
            rows.append({k: _serialize(v) for k, v in row._mapping.items()})

        execution_time_ms = int((time.time() - start_time) * 1000)

        return ExecutorResult(columns, rows, execution_time_ms)
