import os
from sqlalchemy import create_engine, text

def run_migration():
    url = "postgresql+psycopg://ingestion:ingestion@localhost:5442/metadata"
    engine = create_engine(url)
    migration_path = os.path.join("migrations", "003_ai_semantic_layer.sql")
    
    with open(migration_path, "r", encoding="utf-8") as f:
        sql = f.read()

    # Split by semicolon to run statements sequentially, or just run the whole block
    with engine.begin() as conn:
        for stmt in sql.split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
    print("Migration applied successfully.")

if __name__ == "__main__":
    run_migration()
