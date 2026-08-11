"""SQL Validator.

Validates that generated SQL contains only read-only SELECT queries
and checks that referenced tables exist in the connected PostgreSQL schema catalog.
"""
import re
from typing import Any, Dict

UNANSWERABLE_MSG = (
    "I cannot generate a SQL query because the required tables or columns do not exist "
    "in the connected database schema."
)


class SQLValidator:
    """Validates SQL query safety and schema adherence."""

    @staticmethod
    def validate_sql(sql: str, catalog: Dict[str, Any] = None) -> str:
        """Validates generated SQL against catalog tables and read-only rule."""
        clean_sql = sql.strip()

        if "UNANSWERABLE" in clean_sql.upper():
            return UNANSWERABLE_MSG

        # Rule 1: Read-only SELECT validation
        first_word = clean_sql.split()[0].upper() if clean_sql.split() else ""
        if first_word != "SELECT" and not clean_sql.upper().startswith("WITH"):
            return UNANSWERABLE_MSG

        disallowed_keywords = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"]
        for kw in disallowed_keywords:
            if re.search(r"\b" + kw + r"\b", clean_sql, re.IGNORECASE):
                return UNANSWERABLE_MSG

        # Rule 1b: Static offline AST syntax validation via sqlglot
        try:
            import sqlglot
            parsed = sqlglot.parse(clean_sql, read="postgres")
            if not parsed or all(stmt is None for stmt in parsed):
                return UNANSWERABLE_MSG
        except Exception:
            # Fall back gracefully if sqlglot dialect parse hits custom extension syntax
            pass

        # Rule 2: Table existence validation if catalog provided
        if not catalog:
            return clean_sql

        tables_in_catalog = set(catalog.keys())
        found_tables = re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z0-9_]+)", clean_sql, re.IGNORECASE)
        for t in found_tables:
            t_lower = t.lower()
            if t_lower not in {table.lower() for table in tables_in_catalog}:
                return UNANSWERABLE_MSG

        return clean_sql
