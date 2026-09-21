"""Deterministic PostgreSQL safety and schema validation."""

from __future__ import annotations

import re

from dataclasses import dataclass

from typing import Any, Mapping

import structlog

log = structlog.get_logger(__name__)

UNANSWERABLE = "UNANSWERABLE"

@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    sql: str | None = None
    code: str | None = None
    message: str | None = None

SQLGLOT_DIALECTS = {
    "postgres": "postgres",
    "mysql": "mysql",
    "mssql": "tsql",
    "excel": "sqlite",
}

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

MSSQL_INCOMPATIBLE_FUNCTIONS = {
    "date_trunc",
    "date_bucket",
    "time_bucket",
    "to_char",
    "from_unixtime",
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
    def validate_sql_detailed(
        cls,
        sql: str,
        catalog: Mapping[str, Any] | None = None,
        dialect: str = "postgres",
    ) -> ValidationResult:
        """Return a ValidationResult with structured error info."""

        clean_sql = (sql or "").strip()
        dialect_lower = (dialect or "postgres").strip().lower()

        if not clean_sql:
            return ValidationResult(
                valid=False, code="empty_sql",
                message="No SQL provided.",
            )

        if clean_sql.upper() == UNANSWERABLE:
            return ValidationResult(
                valid=False, code="unanswerable",
                message="LLM returned UNANSWERABLE.",
            )

        first_token = clean_sql.split()[0] if clean_sql.split() else ""
        if not clean_sql.upper().startswith(("SELECT", "WITH")):
            log.warning(
                "sql_validation_rejected_non_query",
                first_token=first_token,
            )
            return ValidationResult(
                valid=False, code="non_query",
                message=f"Statement starts with '{first_token}', expected SELECT or WITH.",
            )

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
                    return ValidationResult(
                        valid=False, code="incompatible_function",
                        message=f"Function '{function_name}' is not available in PostgreSQL.",
                    )
        if dialect_lower == "mssql":
            for function_name in MSSQL_INCOMPATIBLE_FUNCTIONS:
                if re.search(
                    rf"\b{re.escape(function_name)}\s*\(",
                    clean_sql,
                    flags=re.IGNORECASE,
                ):
                    return ValidationResult(
                        valid=False,
                        code="incompatible_mssql_function",
                        message=(
                            f"Function '{function_name}' is not supported in Microsoft SQL Server (T-SQL). "
                            "Use DATEFROMPARTS(YEAR(col), MONTH(col), 1), DATEADD/DATEDIFF, or FORMAT instead."
                        ),
                    )


        glot_dialect = SQLGLOT_DIALECTS.get(dialect_lower)

        if glot_dialect is None:
            log.warning(
                "sql_validation_unsupported_dialect",
                dialect=dialect_lower,
            )
            return ValidationResult(
                valid=False, code="unsupported_dialect",
                message=f"Dialect '{dialect_lower}' is not supported.",
            )

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
                return ValidationResult(
                    valid=False, code="multiple_statements",
                    message=f"Expected 1 statement, got {len(statements)}.",
                )

            expression = statements[0]

        except Exception as exc:
            log.warning(
                "sql_validation_parse_failed",
                error=str(exc),
            )
            return ValidationResult(
                valid=False, code="parse_error",
                message=f"SQL parse failed: {exc}",
            )

        for node in expression.walk():
            node_type = type(node).__name__.upper()

            if node_type in BLOCKED_NODE_TYPES:
                log.warning(
                    "sql_validation_blocked_node",
                    node_type=node_type,
                )
                return ValidationResult(
                    valid=False, code="blocked_node",
                    message=f"Destructive operation '{node_type}' is not allowed.",
                )

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
                return ValidationResult(
                    valid=False, code="blocked_function",
                    message=f"Function '{function_name}' is blocked.",
                )

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
            derived_qualifiers: set[str] = set()

            for subquery in expression.find_all(exp.Subquery):
                if subquery.alias_or_name:
                    derived_qualifiers.add(
                        subquery.alias_or_name.lower()
                    )

            for table in expression.find_all(exp.Table):
                table_name = table.name.lower() if table.name else ""

                if not table_name:
                    continue

                if table_name in cte_names:
                    if table.alias_or_name:
                        derived_qualifiers.add(
                            table.alias_or_name.lower()
                        )
                    derived_qualifiers.add(table_name)
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
                    return ValidationResult(
                        valid=False, code="unknown_schema",
                        message=f"Schema '{schema_name}' not found in catalog.",
                    )

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
                    return ValidationResult(
                        valid=False, code="unknown_table",
                        message=f"Table '{qualified_name}' not found in catalog.",
                    )

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

                if (
                    qualifier in cte_names
                    or qualifier in derived_qualifiers
                ):
                    continue

                if qualifier:
                    available_columns = alias_columns.get(qualifier)

                    if available_columns is None:
                        log.warning(
                            "sql_validation_unknown_qualifier",
                            qualifier=qualifier,
                            column_name=column_name,
                        )
                        return ValidationResult(
                            valid=False, code="unknown_qualifier",
                            message=f"Alias '{qualifier}' does not match any table.",
                        )

                    if (
                        available_columns
                        and column_name not in available_columns
                    ):
                        log.warning(
                            "sql_validation_unknown_qualified_column",
                            qualifier=qualifier,
                            column_name=column_name,
                        )
                        return ValidationResult(
                            valid=False, code="unknown_qualified_column",
                            message=f"Alias '{qualifier}' does not expose column '{column_name}'.",
                        )

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
                    return ValidationResult(
                        valid=False, code="unknown_unqualified_column",
                        message=f"Column '{column_name}' not found in any referenced table.",
                    )

                if matching_table_count > 1:
                    log.warning(
                        "sql_validation_ambiguous_unqualified_column",
                        column_name=column_name,
                    )
                    return ValidationResult(
                        valid=False, code="ambiguous_column",
                        message=f"Column '{column_name}' exists in multiple tables; qualify it.",
                    )

            for select_expression in expression.find_all(exp.Select):
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
                            return ValidationResult(
                                valid=False, code="missing_group_by",
                                message=f"Expression '{normalized_projection}' must appear in GROUP BY.",
                            )

        try:
            formatted_sql = expression.sql(
                dialect=glot_dialect,
                pretty=False,
            )
            return ValidationResult(valid=True, sql=formatted_sql)
        except Exception:
            return ValidationResult(valid=True, sql=clean_sql)


    @classmethod
    def validate_sql(
        cls,
        sql: str,
        catalog: Mapping[str, Any] | None = None,
        dialect: str = "postgres",
    ) -> str:
        """Return normalized safe SQL or exactly UNANSWERABLE."""

        result = cls.validate_sql_detailed(sql, catalog=catalog, dialect=dialect)
        return result.sql if result.valid else UNANSWERABLE

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

        glot_dialect = SQLGLOT_DIALECTS.get(dialect_lower)

        if glot_dialect is None:
            log.warning(
                "sql_validation_unsupported_dialect",
                dialect=dialect_lower,
            )
            return UNANSWERABLE

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
            derived_qualifiers: set[str] = set()
 
            for subquery in expression.find_all(exp.Subquery):
                if subquery.alias_or_name:
                    derived_qualifiers.add(
                        subquery.alias_or_name.lower()
                    )

            for table in expression.find_all(exp.Table):
                table_name = table.name.lower() if table.name else ""

                if not table_name:
                    continue

                if table_name in cte_names:
                    if table.alias_or_name:
                        derived_qualifiers.add(
                            table.alias_or_name.lower()
                        )
                    derived_qualifiers.add(table_name)
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
                if (
                    qualifier in cte_names
                    or qualifier in derived_qualifiers
                ):
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

            # Validate aggregates and GROUP BY for this SELECT scope only.
            for select_expression in expression.find_all(exp.Select):
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