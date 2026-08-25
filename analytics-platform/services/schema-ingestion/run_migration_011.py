import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def run_migration():
    url = os.environ.get("METADATA_DB_URL", "postgresql+psycopg://ingestion:ingestion@localhost:5442/metadata")
    engine = create_engine(url)
    migration_path = os.path.join("migrations", "011_domain_processing_status.sql")
    
    with open(migration_path, "r", encoding="utf-8") as f:
        sql = f.read()

    # Split by semicolon to run statements sequentially
    with engine.begin() as conn:
        for stmt in sql.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
    print("Migration 011 applied successfully. The 'processing_status' column was added.")

if __name__ == "__main__":
    run_migration()
