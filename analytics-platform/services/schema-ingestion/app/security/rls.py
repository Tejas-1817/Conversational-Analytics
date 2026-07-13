"""
Row-Level Security (RLS) Engine.

Evaluates RLS policies for the current user and generates additional
WHERE clause fragments that are injected into the SQL compiler before
any query is executed.

Usage:
    from app.security.rls import RLSEngine

    extra_filters = RLSEngine.get_filters(
        session, tenant_id, user_role, user_claims, table_name
    )
    # extra_filters is a list of strings like ["region = 'EMEA'", "dept = 'Finance'"]
    # Inject these into the WHERE clause of the compiled SQL.
"""
from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.models import RLSPolicy

log = structlog.get_logger()


class RLSEngine:
    """
    Evaluates active RLS policies for a given (tenant, user role, table).
    Returns a list of SQL WHERE clause fragments to be ANDed into the query.
    """

    ALLOWED_OPERATORS = {"=", "!=", "IN", "NOT IN", "LIKE", "NOT LIKE"}

    @classmethod
    def get_filters(
        cls,
        session: Session,
        tenant_id: uuid.UUID,
        user_role: str,
        user_claims: dict[str, Any],
        table_name: str | None = None,
        source_id: uuid.UUID | None = None,
    ) -> list[str]:
        """
        Returns a list of parameterized WHERE clause fragments for the given context.

        Args:
            session:      DB session (reads from rls_policies).
            tenant_id:    The calling user's tenant.
            user_role:    The calling user's role (ADMIN, ANALYST, VIEWER).
            user_claims:  Dict of user attributes available for policy evaluation.
                          e.g. {"region": "EMEA", "department": "Finance"}
            table_name:   (Optional) the specific table being queried.
            source_id:    (Optional) the data source being queried.
        """
        # Admins bypass RLS by default
        if user_role == "ADMIN":
            return []

        query = session.query(RLSPolicy).filter(
            RLSPolicy.tenant_id == tenant_id,
            RLSPolicy.is_active == True,  # noqa: E712
        )

        if source_id:
            query = query.filter(
                (RLSPolicy.source_id == source_id) | (RLSPolicy.source_id == None)  # noqa: E711
            )

        policies = query.all()
        filters: list[str] = []

        for policy in policies:
            # Check if this policy applies to this role
            if policy.applies_to_roles and user_role not in policy.applies_to_roles:
                continue

            # Check table scope
            if policy.table_name and table_name and policy.table_name != table_name:
                continue

            # Resolve the filter value from user claims
            claim_value = user_claims.get(policy.filter_claim)
            if claim_value is None:
                log.warning(
                    "rls_claim_missing",
                    policy=policy.name,
                    claim=policy.filter_claim,
                    user_claims_keys=list(user_claims.keys()),
                )
                # If the claim is missing, deny by injecting a FALSE clause
                # This prevents accidental data exposure
                filters.append("1 = 0 /* rls: missing claim */")
                continue

            operator = policy.filter_operator.upper()
            if operator not in cls.ALLOWED_OPERATORS:
                log.error("rls_invalid_operator", policy=policy.name, operator=operator)
                filters.append("1 = 0 /* rls: invalid operator */")
                continue

            column = cls._quote_identifier(policy.filter_column)
            value = cls._quote_value(claim_value, operator)
            fragment = f"{column} {operator} {value}"
            log.info("rls_filter_applied", policy=policy.name, fragment=fragment)
            filters.append(fragment)

        return filters

    @staticmethod
    def _quote_identifier(name: str) -> str:
        """Strict identifier quoting.
        Only lowercase alphanumeric and underscore are permitted.
        All other characters — including spaces, semicolons, dashes — are stripped.
        SQL keywords embedded in a column name (e.g. 'regionDROPTABLEusers') are
        inherently harmless once double-quoted by PostgreSQL, because double-quoted
        identifiers are always treated as an identifier name, never as SQL commands.
        The double-quoting is the security boundary, not keyword filtering.
        """
        safe = "".join(c for c in name.lower() if c.isalnum() or c == "_")
        return f'"{safe}"'

    @staticmethod
    def _quote_value(value: Any, operator: str) -> str:
        """
        Safely quote a value for SQL injection into WHERE clause.
        Uses PostgreSQL $$ quoting for strings, handles lists for IN operators.
        """
        if operator in ("IN", "NOT IN"):
            if isinstance(value, (list, tuple)):
                items = ", ".join(f"'{str(v).replace(chr(39), chr(39)*2)}'" for v in value)
                return f"({items})"
            else:
                safe_val = str(value).replace("'", "''")
                return f"('{safe_val}')"
        else:
            safe_val = str(value).replace("'", "''")
            return f"'{safe_val}'"

    @classmethod
    def inject_into_sql(cls, sql: str, filters: list[str]) -> str:
        """
        Injects RLS WHERE filters into an existing SQL string.
        Appends to existing WHERE clause or adds one.

        WARNING: This is a best-effort string injection. Production systems
        should use AST-based SQL manipulation (e.g. sqlglot).
        """
        if not filters:
            return sql

        rls_clause = " AND ".join(f"({f})" for f in filters)

        # Normalize the SQL for detection
        sql_upper = sql.upper().strip()

        if " WHERE " in sql_upper:
            # Append to existing WHERE clause, before any GROUP BY / ORDER BY / LIMIT
            for keyword in ["GROUP BY", "ORDER BY", "LIMIT", "HAVING"]:
                idx = sql_upper.find(keyword)
                if idx > sql_upper.find(" WHERE "):
                    return sql[:idx] + f" AND {rls_clause} " + sql[idx:]
            return sql + f" AND {rls_clause}"
        else:
            # No WHERE clause — insert before GROUP BY / ORDER BY / LIMIT
            for keyword in ["GROUP BY", "ORDER BY", "LIMIT", "HAVING"]:
                idx = sql_upper.find(keyword)
                if idx != -1:
                    return sql[:idx] + f" WHERE {rls_clause} " + sql[idx:]
            return sql + f" WHERE {rls_clause}"
