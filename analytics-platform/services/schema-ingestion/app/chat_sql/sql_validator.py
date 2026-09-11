"""Deterministic PostgreSQL safety and schema validation."""

from __future__ import annotations

import re

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
    "pg_rotate_logfile",
    "pg_reload_conf",
    "pg_sleep",
    "pg_terminate_backend",
    "set_config",
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "pg_stat_file",
    "current_setting",
}

POSTGRES_INCOMPATIBLE_FUNCTIONS = {
    "date_bucket",
    "time_bucket",
    "date_format",
    "datediff",
    "from_unixtime",
    "ifnull",
    "str_to_date",
    "to_days",
    "unix_timestamp",
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
        dialect: str = "postgres",
    ) -> str:
        """Return normalized safe SQL or exactly UNANSWERABLE."""

        clean_sql = (sql or "").strip()
        dialect_lower = (dialect or "postgres").strip().lower()

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

        if dialect_lower == "postgres":
            for function_name in POSTGRES_INCOMPATIBLE_FUNCTIONS:
                if re.search(
                    rf"\b{re.escape(function_name)}\s*\(",
                    clean_sql,
                    flags=re.IGNORECASE,
                ):
                    log.warning(
                        "sql_validation_non_postgresql_function",
                        function_name=function_name,
                    )
                    return UNANSWERABLE

        # Map dialect to sqlglot dialect identifier
        glot_dialect = "postgres"
        if dialect_lower == "mysql":
            glot_dialect = "mysql"
        elif dialect_lower == "mssql":
            glot_dialect = "tsql"

        try:
            import sqlglot
            from sqlglot import exp

            statements = sqlglot.parse(
                clean_sql,
                read=glot_dialect,
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
            if isinstance(function, exp.Anonymous):
                function_name = function.name.lower()
            else:
                function_name = function.sql_name().lower()

            if function_name in BLOCKED_FUNCTIONS:
                log.warning(
                    "sql_validation_blocked_function",
                    function_name=function_name,
                )
                return UNANSWERABLE

        if catalog:
            normalized_catalog = cls._normalize_catalog(catalog)

            allowed_schemas = {
                table_name.rsplit(".", 1)[0]
                for table_name in normalized_catalog
                if "." in table_name
            }

            cte_names = {
                cte.alias_or_name.lower()
                for cte in expression.find_all(exp.CTE)
                if cte.alias_or_name
            }

            alias_columns: dict[str, set[str]] = {}
            referenced_column_sets: list[set[str]] = []

            for table in expression.find_all(exp.Table):
                table_name = table.name.lower() if table.name else ""

                if not table_name or table_name in cte_names:
                    continue

                schema_name = (
                    table.db.lower()
                    if table.db
                    else ""
                )
                if (
                    schema_name
                    and allowed_schemas
                    and schema_name not in allowed_schemas
                ):
                    log.warning(
                        "sql_validation_unknown_schema",
                        schema_name=schema_name,
                    )
                    return UNANSWERABLE

                qualified_name = (
                    f"{schema_name}.{table_name}"
                    if schema_name
                    else table_name
                )

                if schema_name:
                    columns = normalized_catalog.get(qualified_name)
                else:
                    columns = normalized_catalog.get(table_name)

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
                referenced_column_sets.append(columns)

            select_aliases = {
                alias.alias.lower()
                for alias in expression.find_all(exp.Alias)
                if alias.alias
            }

            for column in expression.find_all(exp.Column):
                column_name = (
                    column.name.lower()
                    if column.name
                    else ""
                )
                qualifier = (
                    column.table.lower()
                    if column.table
                    else ""
                )

                if not column_name or column_name == "*":
                    continue

                # CTE columns and calculated SELECT aliases are validated
                # through their underlying expressions.
                if qualifier in cte_names:
                    continue

                if qualifier:
                    available_columns = alias_columns.get(qualifier)

                    if available_columns is None:
                        log.warning(
                            "sql_validation_unknown_qualifier",
                            qualifier=qualifier,
                            column_name=column_name,
                        )
                        return UNANSWERABLE

                    if (
                        available_columns
                        and column_name not in available_columns
                    ):
                        log.warning(
                            "sql_validation_unknown_qualified_column",
                            qualifier=qualifier,
                            column_name=column_name,
                        )
                        return UNANSWERABLE

                    continue

                if column_name in select_aliases:
                    continue

                matching_table_count = sum(
                    1
                    for available_columns in referenced_column_sets
                    if column_name in available_columns
                )

                if matching_table_count == 0:
                    log.warning(
                        "sql_validation_unknown_unqualified_column",
                        column_name=column_name,
                    )
                    return UNANSWERABLE

                if matching_table_count > 1:
                    log.warning(
                        "sql_validation_ambiguous_unqualified_column",
                        column_name=column_name,
                    )
                    return UNANSWERABLE

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

            # Validate GROUP BY requirements for aggregate queries.
            select_expression = expression.find(exp.Select)

            if select_expression is not None:
                contains_aggregate = any(
                    True
                    for _ in select_expression.find_all(exp.AggFunc)
                )

                if contains_aggregate:
                    group = select_expression.args.get("group")
                    grouped_expressions = {
                        item.sql(dialect=glot_dialect).lower()
                        for item in (group.expressions if group else [])
                    }

                    for projection in select_expression.expressions:
                        projected_expression = (
                            projection.this
                            if isinstance(projection, exp.Alias)
                            else projection
                        )

                        if projected_expression.find(exp.AggFunc):
                            continue

                        if not any(projected_expression.find_all(exp.Column)):
                            continue

                        normalized_projection = projected_expression.sql(
                            dialect=glot_dialect
                        ).lower()

                        if normalized_projection not in grouped_expressions:
                            log.warning(
                                "sql_validation_missing_group_by",
                                expression=normalized_projection,
                            )
                            return UNANSWERABLE

        try:
            return expression.sql(
                dialect=glot_dialect,
                pretty=False,
            )
        except Exception:
            return clean_sql