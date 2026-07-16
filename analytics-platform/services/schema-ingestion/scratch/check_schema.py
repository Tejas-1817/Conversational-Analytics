import os
import psycopg
from dotenv import load_dotenv
load_dotenv()
DB_URL = os.environ.get('METADATA_DB_URL').replace('postgresql+psycopg', 'postgresql')
with psycopg.connect(DB_URL) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'chart_recommendations';")
        for row in cur.fetchall():
            print(row)
