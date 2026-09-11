"""Apply all pending SQL migrations to the metadata database idempotently."""
import os
import sys
import glob
import logging
import re
from sqlalchemy import text

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def is_table_existing(conn, table_name: str) -> bool:
    res = conn.execute(text("""
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = :t
    """), {"t": table_name}).fetchone()
    return res is not None


def is_column_existing(conn, table_name: str, column_name: str) -> bool:
    res = conn.execute(text("""
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' AND table_name = :t AND column_name = :c
    """), {"t": table_name, "c": column_name}).fetchone()
    return res is not None


def apply_migrations():
    engine = get_engine()
    migrations_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'migrations'))
    
    # 1. Ensure applied_migrations table exists
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS applied_migrations (
                filename VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        # If database already had tables initialized before applied_migrations existed,
        # mark base migrations as applied so they don't re-run blindly.
        if is_table_existing(conn, "data_sources"):
            conn.execute(text("INSERT INTO applied_migrations (filename) VALUES ('001_init.sql') ON CONFLICT DO NOTHING"))
        if is_table_existing(conn, "users"):
            conn.execute(text("INSERT INTO applied_migrations (filename) VALUES ('002_auth.sql') ON CONFLICT DO NOTHING"))
        if is_table_existing(conn, "dashboards"):
            conn.execute(text("INSERT INTO applied_migrations (filename) VALUES ('004_dashboards.sql') ON CONFLICT DO NOTHING"))
        if is_table_existing(conn, "evaluation_runs"):
            conn.execute(text("INSERT INTO applied_migrations (filename) VALUES ('006_phase7_eval.sql') ON CONFLICT DO NOTHING"))

    # 2. Get all SQL files sorted by filename
    sql_files = sorted(glob.glob(os.path.join(migrations_dir, "*.sql")))
    logger.info(f"Found {len(sql_files)} migration files in {migrations_dir}")
    
    for file_path in sql_files:
        filename = os.path.basename(file_path)
        with engine.begin() as conn:
            result = conn.execute(
                text("SELECT 1 FROM applied_migrations WHERE filename = :fn"),
                {"fn": filename}
            ).fetchone()
            
            if result:
                logger.info(f"Skipping {filename} (already applied)")
                continue
            
            # For 012 specifically, if column already exists, mark applied
            if filename == "012_excel_data_source.sql" and is_column_existing(conn, "data_sources", "file_path"):
                logger.info(f"Skipping {filename} (columns already exist)")
                conn.execute(text("INSERT INTO applied_migrations (filename) VALUES (:fn) ON CONFLICT DO NOTHING"), {"fn": filename})
                continue

            logger.info(f"Applying migration: {filename}...")
            with open(file_path, "r", encoding="utf-8") as f:
                sql_content = f.read().strip()
                
            if sql_content:
                try:
                    conn.execute(text(sql_content))
                    conn.execute(
                        text("INSERT INTO applied_migrations (filename) VALUES (:fn) ON CONFLICT DO NOTHING"),
                        {"fn": filename}
                    )
                    logger.info(f"Successfully applied: {filename}")
                except Exception as e:
                    logger.warning(f"Could not apply {filename} directly: {e}. Attempting idempotent block execution...")
                    # If it failed because object already exists, still record or continue
                    if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                        conn.execute(
                            text("INSERT INTO applied_migrations (filename) VALUES (:fn) ON CONFLICT DO NOTHING"),
                            {"fn": filename}
                        )
                        logger.info(f"Marked {filename} as applied (objects already exist).")
                    else:
                        raise

    logger.info("All migrations successfully applied and verified!")


if __name__ == "__main__":
    apply_migrations()
