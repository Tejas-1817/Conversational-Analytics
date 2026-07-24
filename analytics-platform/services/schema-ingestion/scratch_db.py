import json
from sqlalchemy import create_engine, text

db_url = 'postgresql+psycopg://ingestion:ingestion@localhost:5442/metadata'
engine = create_engine(db_url)
with engine.connect() as conn:
    res = conn.execute(text("SELECT id, stats FROM ingestion_jobs ORDER BY started_at DESC LIMIT 1")).mappings().fetchone()
    print("Job ID:", res['id'])
    print(json.dumps(res['stats'], indent=2))
