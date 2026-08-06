"""
Connects to a local PostgreSQL server and exports the database schema (DDL)
to a .sql file.

Usage:
    python export_postgres_schema.py
    python export_postgres_schema.py --output my_schema.sql

Connection details are loaded from a local .env file (and can be overridden by
CLI flags or process environment variables):
    PGHOST (default: localhost)
    PGPORT (default: 5432)
    PGDATABASE
    PGUSER
    PGPASSWORD

Strategy:
    1. If the `pg_dump` executable is available on PATH, use it to produce an
       exact, schema-only DDL dump (most accurate, includes constraints,
       sequences, views, etc.).
    2. Otherwise, fall back to reflecting the database with SQLAlchemy and
       reconstructing CREATE TABLE / CREATE INDEX statements.
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.schema import CreateIndex, CreateTable

# Load variables from .env sitting next to this script (does not override
# already-set process environment variables).
load_dotenv(Path(__file__).resolve().parent / ".env")


def build_database_url(params: dict) -> str:
    return (
        f"postgresql+psycopg2://{params['user']}:{params['password']}"
        f"@{params['host']}:{params['port']}/{params['dbname']}"
    )


def dump_with_pg_dump(params: dict, output_file: str, schema: str) -> bool:
    """Try to export the schema using the pg_dump CLI tool. Returns True on success."""
    pg_dump_path = shutil.which("pg_dump")
    if not pg_dump_path:
        print("pg_dump not found on PATH, will fall back to SQLAlchemy reflection.")
        return False

    env = os.environ.copy()
    if params["password"]:
        env["PGPASSWORD"] = params["password"]

    command = [
        pg_dump_path,
        "--schema-only",
        "--no-owner",
        "--no-privileges",
        "--schema", schema,
        "-h", params["host"],
        "-p", str(params["port"]),
        "-U", params["user"],
        "-d", params["dbname"],
    ]

    try:
        result = subprocess.run(command, env=env, capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, OSError) as exc:
        message = exc.stderr if hasattr(exc, "stderr") and exc.stderr else str(exc)
        print(f"pg_dump failed ({message}); falling back to SQLAlchemy reflection.")
        return False

    Path(output_file).write_text(result.stdout, encoding="utf-8")
    print(f"Schema DDL exported via pg_dump to '{output_file}'")
    return True


def dump_with_sqlalchemy(params: dict, output_file: str, schema: str) -> None:
    """Fallback: reflect the database with SQLAlchemy and rebuild DDL statements."""
    database_url = build_database_url(params)
    engine = create_engine(database_url)

    metadata = MetaData()
    try:
        with engine.connect():
            metadata.reflect(bind=engine, schema=schema)
    except SQLAlchemyError as exc:
        raise RuntimeError(f"Failed to connect to the database or reflect schema: {exc}") from exc

    if not metadata.sorted_tables:
        print(f"No tables found in schema '{schema}'.")

    statements = []
    for table in metadata.sorted_tables:
        create_stmt = str(CreateTable(table).compile(engine)).strip()
        statements.append(create_stmt + ";")
        for index in table.indexes:
            index_stmt = str(CreateIndex(index).compile(engine)).strip()
            statements.append(index_stmt + ";")

    ddl_text = "\n\n".join(statements) + "\n"
    Path(output_file).write_text(ddl_text, encoding="utf-8")
    print(f"Schema DDL exported via SQLAlchemy reflection to '{output_file}'")


def export_schema(
    params: dict,
    output_file: str = "database_schema.sql",
    schema: str = "public",
    force_fallback: bool = False,
) -> dict:
    """
    Export a schema-only DDL dump to `output_file`.

    Returns a dict with keys: method, output_file, schema.
    Raises RuntimeError on connection/export failure.
    """
    output_path = Path(output_file)
    if not output_path.is_absolute():
        output_path = Path(__file__).resolve().parent / output_path

    if not force_fallback and dump_with_pg_dump(params, str(output_path), schema):
        return {"method": "pg_dump", "output_file": str(output_path), "schema": schema}

    dump_with_sqlalchemy(params, str(output_path), schema)
    return {"method": "sqlalchemy", "output_file": str(output_path), "schema": schema}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export PostgreSQL schema DDL to a file.")
    parser.add_argument("--host", default=os.getenv("PGHOST", "localhost"), help="Database host (default: localhost)")
    parser.add_argument("--port", default=os.getenv("PGPORT", "5432"), help="Database port (default: 5432)")
    parser.add_argument("--dbname", default=os.getenv("PGDATABASE", "postgres"), help="Database name")
    parser.add_argument("--user", default=os.getenv("PGUSER", "postgres"), help="Database user")
    parser.add_argument("--password", default=os.getenv("PGPASSWORD", ""), help="Database password")
    parser.add_argument("--schema", default="public", help="Postgres schema to export (default: public)")
    parser.add_argument("--output", default="database_schema.sql", help="Output file path (default: database_schema.sql)")
    parser.add_argument(
        "--force-fallback",
        action="store_true",
        help="Skip pg_dump and always use SQLAlchemy reflection",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    params = {
        "host": args.host,
        "port": args.port,
        "dbname": args.dbname,
        "user": args.user,
        "password": args.password,
    }

    try:
        result = export_schema(
            params,
            output_file=args.output,
            schema=args.schema,
            force_fallback=args.force_fallback,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Done ({result['method']}): {result['output_file']}")


if __name__ == "__main__":
    main()
