import psycopg

conn = psycopg.connect("postgresql://ingestion:ingestion@localhost:5442/metadata")

# Read migration
sql = open("migrations/005_phase6_security.sql").read()

# Remove the conversations index since that table doesn't exist in this DB yet
# The FK line references users table (which does exist)
sql_safe = sql.replace(
    "CREATE INDEX IF NOT EXISTS idx_conversations_tenant     ON conversations (tenant_id);\n",
    "-- idx_conversations_tenant skipped (conversations table not yet created)\n"
)

cur = conn.cursor()
cur.execute(sql_safe)
conn.commit()
print("Migration 005 applied successfully!")

# Verify new tables
cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename IN ('tenants', 'rls_policies', 'column_security_policies', 'api_keys', 'oidc_providers', 'tenant_policies') ORDER BY tablename")
new_tables = [r[0] for r in cur.fetchall()]
print("New Phase 6 tables:", new_tables)

conn.close()
