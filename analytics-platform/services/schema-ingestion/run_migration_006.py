import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.environ.get("METADATA_DB_URL")
if not DB_URL:
    print("METADATA_DB_URL not set")
    exit(1)
    
if DB_URL.startswith("postgresql+psycopg"):
    DB_URL = DB_URL.replace("postgresql+psycopg", "postgresql")

with open("migrations/006_phase7_eval.sql", "r") as f:
    sql = f.read()

with psycopg.connect(DB_URL) as conn:
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    print("Successfully ran migration 006_phase7_eval.sql")
