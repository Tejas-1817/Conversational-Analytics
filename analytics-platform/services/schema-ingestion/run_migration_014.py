import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def run_migration():
    url = os.environ.get("METADATA_DB_URL", "postgresql+psycopg://ingestion:ingestion@localhost:5442/metadata")
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    
    print("1. Adding missing enum values to 'source_type'...")
    enum_values = ['mssql', 'excel', 'snowflake', 'bigquery', 'sqlite']
    with engine.connect() as conn:
        for val in enum_values:
            try:
                conn.execute(text(f"ALTER TYPE source_type ADD VALUE IF NOT EXISTS '{val}'"))
                print(f"   Added enum value: {val}")
            except Exception as e:
                print(f"   Notice for enum {val}: {e}")

    print("2. Adding missing columns to 'data_sources' table...")
    columns_sql = [
        "ALTER TABLE data_sources ADD COLUMN IF NOT EXISTS secret_ref TEXT",
        "ALTER TABLE data_sources ADD COLUMN IF NOT EXISTS credential_version INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE data_sources ADD COLUMN IF NOT EXISTS ssl_mode TEXT NOT NULL DEFAULT 'verify-full'",
        "ALTER TABLE data_sources ADD COLUMN IF NOT EXISTS connection_status TEXT NOT NULL DEFAULT 'pending'",
        "ALTER TABLE data_sources ADD COLUMN IF NOT EXISTS schema_status TEXT NOT NULL DEFAULT 'pending'",
        "ALTER TABLE data_sources ADD COLUMN IF NOT EXISTS embedding_status TEXT NOT NULL DEFAULT 'pending'",
        "ALTER TABLE data_sources ADD COLUMN IF NOT EXISTS last_connection_error_code TEXT",
        "ALTER TABLE data_sources ADD COLUMN IF NOT EXISTS last_connection_test_at TIMESTAMPTZ",
        "ALTER TABLE data_sources ADD COLUMN IF NOT EXISTS file_path TEXT",
        "ALTER TABLE data_sources ADD COLUMN IF NOT EXISTS original_upload_path TEXT",
        "ALTER TABLE data_sources ALTER COLUMN database_name DROP NOT NULL",
        "ALTER TABLE data_sources ALTER COLUMN username DROP NOT NULL",
        "ALTER TABLE data_sources ALTER COLUMN credentials_encrypted DROP NOT NULL",
        "ALTER TABLE data_sources DROP CONSTRAINT IF EXISTS chk_data_sources_type_credentials",
    ]

    with engine.connect() as conn:
        for stmt in columns_sql:
            try:
                conn.execute(text(stmt))
            except Exception as e:
                print(f"   Notice for column stmt: {e}")

    print("3. Updating constraint chk_data_sources_type_credentials...")
    constraint_sql = """
    ALTER TABLE data_sources
        ADD CONSTRAINT chk_data_sources_type_credentials
        CHECK (
            (
                type::text IN ('postgres', 'mysql', 'mssql')
                AND host IS NOT NULL
                AND database_name IS NOT NULL
                AND username IS NOT NULL
                AND (
                    credentials_encrypted IS NOT NULL
                    OR secret_ref IS NOT NULL
                )
            )
            OR (
                type::text = 'excel'
                AND original_upload_path IS NOT NULL
            )
            OR type::text IN ('snowflake', 'bigquery', 'sqlite')
        )
    """
    with engine.connect() as conn:
        try:
            conn.execute(text(constraint_sql))
            print("   Constraint applied successfully.")
        except Exception as e:
            print(f"   Notice for constraint: {e}")

    print("\n✅ Migration 014 applied successfully!")

if __name__ == "__main__":
    run_migration()
