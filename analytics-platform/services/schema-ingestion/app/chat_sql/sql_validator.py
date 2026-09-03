"""Deterministic PostgreSQL safety and schema validation."""

from __future__ import annotations

from typing import Any, Mapping

import structlog

log = structlog.get_logger(__name__)

UNANSWERABLE = "UNANSWERABLE"

BLOCKED_NODE_TYPES = {
    "ALTER",
    "COMMAND",
    "COPY",
    "CREATE",
    "DELETE",
    "DROP",
    "GRANT",
    "INSERT",
    "INTO",
    "LOCK",
    "MERGE",
    "REVOKE",
    "TRANSACTION",
    "TRUNCATE",
    "UPDATE",
    "USE",
}

BLOCKED_FUNCTIONS = {
    "dblink_exec",
    "lo_export",
    "lo_import",
    "pg_cancel_backend",
    "pg_reload_conf",
    "pg_rotate_logfile",
    "pg_sleep",
    "pg_terminate_backend",
    "set_config",
}


class SQLValidator:
    """Validate generated SQL before customer-database execution."""

    @staticmethod
    def _normalize_catalog(
        catalog: Mapping[str, Any],
    ) -> dict[str, set[str]]:
        """Normalize table and column names to lowercase."""

        normalized: dict[str, set[str]] = {}

        for table_name, raw_columns in catalog.items():
            full_name = str(table_name).strip().lower()
            simple_name = full_name.split(".")[-1]

            if isinstance(raw_columns, Mapping):
                columns = {
                    str(column).strip().lower()
                    for column in raw_columns.keys()
                }
            elif isinstance(raw_columns, (set, list, tuple)):
                columns = {
                    str(column).strip().lower()
                    for column in raw_columns
                }
            else:
                columns = set()

            normalized[full_name] = columns
            normalized[simple_name] = columns

        return normalized

    @classmethod
    def validate_sql(
        cls,
        sql: str,
        catalog: Mapping[str, Any] | None = None,
    ) -> str:
        """Return normalized safe SQL or exactly UNANSWERABLE."""

        clean_sql = (sql or "").strip()

        if not clean_sql:
            return UNANSWERABLE

        if clean_sql.upper() == UNANSWERABLE:
            return UNANSWERABLE

        if not clean_sql.upper().startswith(("SELECT", "WITH")):
            log.warning(
                "sql_validation_rejected_non_query",
                first_token=clean_sql.split()[0] if clean_sql.split() else "",
            )
            return UNANSWERABLE

        try:
            import sqlglot
            from sqlglot import exp

            statements = sqlglot.parse(
                clean_sql,
                read="postgres",
            )

            if len(statements) != 1 or statements[0] is None:
                log.warning(
                    "sql_validation_rejected_statement_count",
                    statement_count=len(statements),
                )
                return UNANSWERABLE

            expression = statements[0]

        except Exception as exc:
            log.warning(
                "sql_validation_parse_failed",
                error=str(exc),
            )
            return UNANSWERABLE

        for node in expression.walk():
            node_type = type(node).__name__.upper()

            if node_type in BLOCKED_NODE_TYPES:
                log.warning(
                    "sql_validation_blocked_node",
                    node_type=node_type,
                )
                return UNANSWERABLE

        for function in expression.find_all(exp.Func):
            function_name = function.sql_name().lower()

            if function_name in BLOCKED_FUNCTIONS:
                log.warning(
                    "sql_validation_blocked_function",
                    function_name=function_name,
                )
                return UNANSWERABLE

        if catalog:
            normalized_catalog = cls._normalize_catalog(catalog)

            cte_names = {
                cte.alias_or_name.lower()
                for cte in expression.find_all(exp.CTE)
                if cte.alias_or_name
            }

            alias_columns: dict[str, set[str]] = {}

            for table in expression.find_all(exp.Table):
                table_name = table.name.lower() if table.name else ""

                if not table_name or table_name in cte_names:
                    continue

                schema_name = (
                    table.db.lower()
                    if table.db
                    else ""
                )

                qualified_name = (
                    f"{schema_name}.{table_name}"
                    if schema_name
                    else table_name
                )

                columns = (
                    normalized_catalog.get(qualified_name)
                    or normalized_catalog.get(table_name)
                )

                if columns is None:
                    log.warning(
                        "sql_validation_unknown_table",
                        table_name=qualified_name,
                    )
                    return UNANSWERABLE

                alias_name = (
                    table.alias_or_name.lower()
                    if table.alias_or_name
                    else table_name
                )

                alias_columns[alias_name] = columns
                alias_columns[table_name] = columns

            # Validate qualified columns such as c.customer_id.
            # Unqualified columns are left to PostgreSQL because they may
            # refer to CTE outputs or SELECT aliases.
            for column in expression.find_all(exp.Column):
                column_name = column.name.lower() if column.name else ""
                qualifier = column.table.lower() if column.table else ""

                if (
                    not column_name
                    or column_name == "*"
                    or not qualifier
                    or qualifier in cte_names
                ):
                    continue

                available_columns = alias_columns.get(qualifier)

                if (
                    available_columns is not None
                    and available_columns
                    and column_name not in available_columns
                ):
                    log.warning(
                        "sql_validation_unknown_qualified_column",
                        qualifier=qualifier,
                        column_name=column_name,
                    )
                    return UNANSWERABLE

        try:
            return expression.sql(
                dialect="postgres",
                pretty=False,
            )
        except Exception:
            return clean_sql