"""
verify_sql.py

Checks a SQL query for syntax errors before it's ever run — the last
safety step after generate_sql.py produces a query.

Two modes:
  1. Static check (default): parses the SQL using sqlglot's dialect-aware
     grammar. No database connection needed, works offline, catches
     genuine syntax errors (missing parens, bad keywords, malformed
     clauses, etc).
  2. Live check (--db-url): additionally runs `EXPLAIN <query>` against
     a real database. This is a stronger check — it also catches errors
     sqlglot can't (e.g. a column that doesn't exist) — but requires a
     reachable DB and never executes/modifies data (EXPLAIN only plans
     the query, it doesn't run it).

Usage:
    python verify_sql.py "SELECT * FROM orders;"
    python verify_sql.py --file query.sql
    echo "SELECT * FROM orders;" | python verify_sql.py
    python verify_sql.py "SELECT * FROM orders;" --dialect postgres
    python verify_sql.py "SELECT * FROM orders;" --db-url postgresql+psycopg2://user:pass@localhost:5432/db
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

import sqlglot
from sqlglot.errors import ParseError


@dataclass
class SyntaxCheckResult:
    is_valid: bool
    dialect: str
    error: str | None = None
    error_line: int | None = None
    error_column: int | None = None
    normalized_sql: str | None = None  # sqlglot's re-rendered version, if valid


def check_syntax(sql: str, dialect: str = "postgres") -> SyntaxCheckResult:
    """Static, offline syntax check via sqlglot. Does not need a DB."""
    if not sql or not sql.strip():
        return SyntaxCheckResult(is_valid=False, dialect=dialect, error="Empty SQL string")

    try:
        parsed = sqlglot.parse(sql, read=dialect)
        if not parsed or all(stmt is None for stmt in parsed):
            return SyntaxCheckResult(is_valid=False, dialect=dialect, error="No valid SQL statement found")

        normalized = "; ".join(stmt.sql(dialect=dialect) for stmt in parsed if stmt is not None)
        return SyntaxCheckResult(is_valid=True, dialect=dialect, normalized_sql=normalized)

    except ParseError as e:
        # sqlglot's errors carry structured location info in e.errors
        first_error = e.errors[0] if getattr(e, "errors", None) else {}
        return SyntaxCheckResult(
            is_valid=False,
            dialect=dialect,
            error=str(e),
            error_line=first_error.get("line"),
            error_column=first_error.get("col"),
        )
    except Exception as e:
        return SyntaxCheckResult(is_valid=False, dialect=dialect, error=f"Unexpected parsing error: {e}")


def check_syntax_live(sql: str, db_url: str) -> SyntaxCheckResult:
    """Stronger check: asks the real database to plan the query via
    EXPLAIN, without executing it. Catches things static parsing can't
    (unknown tables/columns, type mismatches) but requires connectivity.
    """
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import SQLAlchemyError

    cleaned = sql.strip().rstrip(";")
    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            conn.execute(text(f"EXPLAIN {cleaned}"))
        return SyntaxCheckResult(is_valid=True, dialect="live-db")
    except SQLAlchemyError as e:
        return SyntaxCheckResult(is_valid=False, dialect="live-db", error=str(e).split("\n")[0])
    finally:
        engine.dispose()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check a SQL query for syntax errors")
    parser.add_argument("sql", type=str, nargs="?", default=None, help="SQL query to check (or use --file / stdin)")
    parser.add_argument("--file", type=str, default=None, help="Read the SQL query from a file instead")
    parser.add_argument("--dialect", type=str, default="postgres", help="SQL dialect for static parsing (default: postgres). Others: mysql, sqlite, tsql, bigquery, snowflake, etc.")
    parser.add_argument("--db-url", type=str, default=None, help="If provided, also runs a live EXPLAIN check against this DB (SQLAlchemy connection string). Never executes/modifies data.")
    return parser


def read_input_sql(args) -> str:
    if args.sql is not None:
        return args.sql
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            return f.read()
    if not sys.stdin.isatty():
        return sys.stdin.read()
    print("Error: provide SQL as an argument, --file, or via stdin.", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    args = build_arg_parser().parse_args()
    sql = read_input_sql(args)

    static_result = check_syntax(sql, dialect=args.dialect)

    print(f"--- Static syntax check ({args.dialect}) ---")
    if static_result.is_valid:
        print("VALID")
        print(f"Normalized: {static_result.normalized_sql}")
    else:
        print("INVALID")
        print(f"Error: {static_result.error}")
        if static_result.error_line is not None:
            print(f"Location: line {static_result.error_line}, column {static_result.error_column}")

    overall_valid = static_result.is_valid

    if args.db_url:
        print(f"\n--- Live EXPLAIN check ---")
        live_result = check_syntax_live(sql, args.db_url)
        if live_result.is_valid:
            print("VALID (query plans successfully)")
        else:
            print("INVALID")
            print(f"Error: {live_result.error}")
        overall_valid = overall_valid and live_result.is_valid

    sys.exit(0 if overall_valid else 1)


if __name__ == "__main__":
    main()