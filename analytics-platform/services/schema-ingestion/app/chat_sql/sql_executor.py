"""Safe execution of validated SQL against a customer data source."""

from __future__ import annotations

import time
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlalchemy import text

from app.connectors.factory import build_engine
from app.models import DataSource

log = structlog.get_logger(__name__)

ExecutionResult = Tuple[
    List[Dict[str, Any]],
    int,
    float,
    List[str],
    Optional[str],
]


class SQLExecutor:
    """Execute validated read-only SQL against the customer database."""

    @staticmethod
    def execute_query(
        sql: str,
        source: Optional[DataSource] = None,
        limit: int = 100,
        timeout_ms: int = 5_000,
    ) -> ExecutionResult:
        """Return rows, row count, time, columns, and optional error."""

        clean_sql = (sql or "").strip()

        if clean_sql.upper() == "UNANSWERABLE":
            return [], 0, 0.0, [], None

        if not clean_sql.upper().startswith(("SELECT", "WITH")):
            return (
                [],
                0,
                0.0,
                [],
                "Executor rejected SQL that was not a SELECT/WITH query.",
            )

        if source is None:
            return (
                [],
                0,
                0.0,
                [],
                "No connected customer data source was provided.",
            )

        started_at = time.perf_counter()
        engine = None

        try:
            engine = build_engine(source)

        except Exception as exc:
            elapsed_ms = round(
                (time.perf_counter() - started_at) * 1000,
                2,
            )

            error = (
                f"Unable to connect to customer data source "
                f"{source.name!r}: {type(exc).__name__}: {exc}"
            )

            log.error(
                "customer_datasource_connection_failed",
                source_id=str(source.id),
                source_name=source.name,
                error=error,
            )

            return [], 0, elapsed_ms, [], error

        try:
            with engine.connect() as connection:
                source_type = str(source.type).lower()

                # Explicit transaction-level protection ensures that even
                # a previously pooled connection is read-only.
                if source_type == "postgres":
                    connection.execute(
                        text("SET TRANSACTION READ ONLY")
                    )
                    connection.execute(
                        text(
                            f"SET LOCAL statement_timeout = "
                            f"{int(timeout_ms)}"
                        )
                    )

                    database_name = connection.execute(
                        text("SELECT current_database()")
                    ).scalar_one()

                    schema_name = connection.execute(
                        text("SELECT current_schema()")
                    ).scalar_one()

                elif source_type == "mysql":
                    connection.execute(
                        text("SET TRANSACTION READ ONLY")
                    )
                    connection.execute(
                        text(
                            f"SET SESSION max_execution_time = "
                            f"{int(timeout_ms)}"
                        )
                    )

                    database_name = connection.execute(
                        text("SELECT DATABASE()")
                    ).scalar_one()

                    schema_name = database_name

                else:
                    return (
                        [],
                        0,
                        0.0,
                        [],
                        f"Unsupported source type: {source.type}",
                    )

                log.info(
                    "sql_execution_connection_verified",
                    tenant_id=str(source.tenant_id),
                    source_id=str(source.id),
                    source_name=source.name,
                    database_name=database_name,
                    schema_name=schema_name,
                )

                result = connection.execute(text(clean_sql))
                columns = list(result.keys())
                rows = result.fetchmany(limit)

                def serialize(value: Any) -> Any:
                    if value is None:
                        return None

                    if isinstance(value, bool):
                        return value

                    if isinstance(value, Decimal):
                        if value % 1 == 0:
                            return int(value)
                        return float(value)

                    if isinstance(value, (datetime, date)):
                        return value.isoformat()

                    if isinstance(value, uuid.UUID):
                        return str(value)

                    if isinstance(value, (int, float, str)):
                        return value

                    return str(value)

                result_data = [
                    {
                        column: serialize(value)
                        for column, value in zip(columns, row)
                    }
                    for row in rows
                ]

                elapsed_ms = round(
                    (time.perf_counter() - started_at) * 1000,
                    2,
                )

                log.info(
                    "sql_execution_completed",
                    source_id=str(source.id),
                    database_name=database_name,
                    rows_returned=len(result_data),
                    column_names=columns,
                    execution_time_ms=elapsed_ms,
                )

                return (
                    result_data,
                    len(result_data),
                    elapsed_ms,
                    columns,
                    None,
                )

        except Exception as exc:
            elapsed_ms = round(
                (time.perf_counter() - started_at) * 1000,
                2,
            )

            error = f"{type(exc).__name__}: {exc}"

            log.error(
                "sql_execution_failed",
                source_id=str(source.id),
                error=error,
                execution_time_ms=elapsed_ms,
                exc_info=True,
            )

            return [], 0, elapsed_ms, [], error

        finally:
            if engine is not None:
                try:
                    engine.dispose()
                except Exception:
                    pass