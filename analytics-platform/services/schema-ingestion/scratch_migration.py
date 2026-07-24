import os
from sqlalchemy import create_engine, text

def apply():
    db_url = os.getenv("METADATA_DB_URL", "postgresql+psycopg://ingestion:ingestion@localhost:5442/metadata")
    engine = create_engine(db_url)
    with engine.connect() as conn:
        try:
            conn.execute(text("COMMIT"))
            conn.execute(text("ALTER TYPE job_status ADD VALUE 'succeeded_with_warnings'"))
            conn.execute(text("COMMIT"))
            print("Successfully added 'succeeded_with_warnings' to job_status enum.")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate key" in str(e).lower():
                print("Enum value 'succeeded_with_warnings' already exists.")
            else:
                print(f"Error adding enum value: {e}")
                
if __name__ == "__main__":
    apply()
