from app.db import get_engine
from sqlalchemy import text

e = get_engine().execution_options(isolation_level="AUTOCOMMIT")
with e.connect() as conn:
    try:
        conn.execute(text("CREATE USER readonly_user WITH PASSWORD 'readonly';"))
    except Exception as e:
        print(f"User might exist: {e}")
    conn.execute(text("GRANT CONNECT ON DATABASE metadata TO readonly_user;"))
    conn.execute(text("GRANT USAGE ON SCHEMA public TO readonly_user;"))
    conn.execute(text("GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_user;"))
    conn.execute(text("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO readonly_user;"))

print("Read-only user created/granted!")
