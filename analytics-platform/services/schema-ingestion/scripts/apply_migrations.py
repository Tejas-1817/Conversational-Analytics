"""Safely apply the metadata repair migrations.

Important:
- Migration 013 is committed before migration 014 starts.
- A failed migration is never recorded as applied.
- Existing/duplicate errors are not silently ignored.
- Only the explicitly listed repair migrations are executed.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine


SERVICE_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = SERVICE_ROOT / "migrations"

if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.db import get_engine  # noqa: E402


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


# Explicit order is critical:
# PostgreSQL must commit new enum values before migration 014 uses them.
MIGRATIONS = (
    "013_add_source_type_values.sql",
    "014_reconsile_data_sources.sql",
)


def split_repair_migration(sql_content: str) -> list[str]:
    """Split the simple DDL statements used by migrations 013 and 014.

    This intentionally rejects dollar-quoted SQL because splitting such SQL
    requires a real migration/parser framework such as Alembic.
    """
    if "$$" in sql_content:
        raise RuntimeError(
            "Dollar-quoted SQL is not supported by this repair runner. "
            "Use Alembic for this migration."
        )

    return [
        statement.strip()
        for statement in sql_content.split(";")
        if statement.strip()
    ]


def ensure_migration_table(engine: Engine) -> None:
    """Create the migration history table in its own committed transaction."""
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS applied_migrations (
                    filename TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )


def apply_one_migration(engine: Engine, filename: str) -> None:
    migration_path = MIGRATIONS_DIR / filename

    if not migration_path.is_file():
        raise FileNotFoundError(
            f"Migration file does not exist: {migration_path}"
        )

    sql_content = migration_path.read_text(encoding="utf-8")
    statements = split_repair_migration(sql_content)

    if not statements:
        raise RuntimeError(f"Migration is empty: {filename}")

    # Each call gets a separate transaction. Therefore 013 commits before
    # this function is called for 014.
    with engine.begin() as conn:
        # Prevent two application instances from applying the same migration
        # concurrently.
        conn.execute(
            text(
                """
                SELECT pg_advisory_xact_lock(
                    hashtext('schema_ingestion_metadata_migrations')
                )
                """
            )
        )

        already_applied = conn.execute(
            text(
                """
                SELECT 1
                FROM applied_migrations
                WHERE filename = :filename
                """
            ),
            {"filename": filename},
        ).scalar_one_or_none()

        if already_applied is not None:
            logger.info("Skipping already applied migration: %s", filename)
            return

        logger.info("Applying migration: %s", filename)

        for statement in statements:
            conn.exec_driver_sql(statement)

        # This is recorded only after every statement succeeds. If anything
        # fails, engine.begin() rolls back the DDL and this INSERT.
        conn.execute(
            text(
                """
                INSERT INTO applied_migrations (filename)
                VALUES (:filename)
                """
            ),
            {"filename": filename},
        )

        logger.info("Migration applied successfully: %s", filename)


def apply_migrations() -> None:
    engine = get_engine()

    try:
        ensure_migration_table(engine)

        for filename in MIGRATIONS:
            apply_one_migration(engine, filename)
    finally:
        engine.dispose()


if __name__ == "__main__":
    apply_migrations()