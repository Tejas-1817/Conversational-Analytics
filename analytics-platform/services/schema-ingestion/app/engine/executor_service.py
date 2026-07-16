import time

from sqlalchemy import text
from sqlalchemy.orm import Session

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
        rows = [dict(row._mapping) for row in result.fetchall()]

        execution_time_ms = int((time.time() - start_time) * 1000)

        return ExecutorResult(columns, rows, execution_time_ms)
