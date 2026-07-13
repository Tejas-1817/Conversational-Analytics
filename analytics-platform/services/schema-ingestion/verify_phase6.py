import os
os.environ["SECRET_BACKEND"] = "env"
os.environ["ENCRYPTION_KEY"] = "F8v2h0w0D2B-d_jZkXqKkZ0f_wFhD2b0D2B-d_jZkXo=" # Dummy fernet key

import uuid
import structlog
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.main import app
from app.db import get_engine
from app.models import (
    Tenant, User, Dashboard, Conversation, 
    ApiKey, AuditLog, RLSPolicy, ColumnSecurityPolicy
)
from app.security.auth import get_password_hash

# Silence structlog for clean output
structlog.configure(
    processors=[structlog.processors.JSONRenderer()],
    logger_factory=structlog.PrintLoggerFactory(),
)

client = TestClient(app)
engine = get_engine()

# Helper to capture and print verification evidence
print("\n" + "="*80)
print("PHASE 6 VERIFICATION SCRIPT STARTING")
print("="*80 + "\n")

def run_verifications():
    with Session(engine) as session:
        # --- SETUP: Create Tenants & Users ---
        tenant_a_id = uuid.uuid4()
        tenant_b_id = uuid.uuid4()
        
        suffix = uuid.uuid4().hex[:6]
        tenant_a = Tenant(id=tenant_a_id, name=f"Tenant A {suffix}", slug=f"tenant-a-{suffix}", created_by="sys")
        tenant_b = Tenant(id=tenant_b_id, name=f"Tenant B {suffix}", slug=f"tenant-b-{suffix}", created_by="sys")
        
        user_a = User(id=uuid.uuid4(), tenant_id=tenant_a_id, email=f"a_{suffix}@tenant.com", password_hash=get_password_hash("pass"), role="ADMIN")
        user_b = User(id=uuid.uuid4(), tenant_id=tenant_b_id, email=f"b_{suffix}@tenant.com", password_hash=get_password_hash("pass"), role="ADMIN")
        
        session.add_all([tenant_a, tenant_b, user_a, user_b])
        session.commit()
        
        # Authenticate
        token_a = client.post("/auth/login", data={"username": f"a_{suffix}@tenant.com", "password": "pass"}).json()["access_token"]
        token_b = client.post("/auth/login", data={"username": f"b_{suffix}@tenant.com", "password": "pass"}).json()["access_token"]
        
        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # ---------------------------------------------------------
        # 1. Tenant Isolation: Dashboards
        # ---------------------------------------------------------
        print("1. TENANT ISOLATION: DASHBOARDS")
        d_a = Dashboard(id=uuid.uuid4(), tenant_id=tenant_a_id, name="Dashboard A", user_id=user_a.id)
        session.add(d_a)
        session.commit()
        
        # User A accesses Dashboard A
        r1 = client.get(f"/dashboards/{d_a.id}", headers=headers_a)
        print(f"   [User A -> Dashboard A]: {r1.status_code}")
        
        # User B attempts to access Dashboard A
        r2 = client.get(f"/dashboards/{d_a.id}", headers=headers_b)
        print(f"   [User B -> Dashboard A]: {r2.status_code} {r2.json()}")
        print("-" * 50)

        # ---------------------------------------------------------
        # 2. Tenant Isolation: Semantic Models (Metrics/Dimensions)
        # ---------------------------------------------------------
        # We don't have endpoints explicitly mapped in this test scope for semantic models right now,
        # but let's test via the list endpoint to see isolation works
        print("2. TENANT ISOLATION: DATA SOURCES")
        from app.models import DataSource
        from app.security.crypto import encrypt_secret
        src_a = DataSource(id=uuid.uuid4(), tenant_id=tenant_a_id, name="DB A", type="postgres", host="localhost", database_name="db", username="u", credentials_encrypted=encrypt_secret("p"), created_by=str(user_a.id), updated_by=str(user_a.id))
        session.add(src_a)
        session.commit()
        
        r1 = client.get("/sources", headers=headers_a)
        r2 = client.get("/sources", headers=headers_b)
        print(f"   [User A sources count]: {len(r1.json())}")
        print(f"   [User B sources count]: {len(r2.json())}")
        print("-" * 50)



        # ---------------------------------------------------------
        # 4. RLS & 5. Column Masking
        # ---------------------------------------------------------
        print("4 & 5. RLS & COLUMN MASKING")
        from app.security.rls import RLSEngine
        from app.security.column_security import ColumnSecurityEngine
        
        filters = RLSEngine.get_filters(session, tenant_b_id, "VIEWER", {"region": "US"}, "sales")
        print(f"   [RLS Base Filters (No Policies)]: {filters}")
        
        # Add a policy
        rp = RLSEngine.inject_into_sql("SELECT * FROM sales", ["\"region\" = 'US'"])
        print(f"   [RLS SQL Injection]: {rp}")
        
        out_cols, out_rows = ColumnSecurityEngine.apply(session, tenant_b_id, "VIEWER", "sales", ["name", "salary"], [{"name": "Bob", "salary": 100000}])
        print(f"   [CLS Base Masking (No Policies)]: cols={out_cols}, salary={out_rows[0].get('salary')}")
        print("-" * 50)

        # ---------------------------------------------------------
        # 6. OIDC Login
        # ---------------------------------------------------------
        print("6. OIDC SSO")
        r = client.get("/auth/oidc/login")
        print(f"   [OIDC Redirect Status]: {r.status_code}")
        # Note: can't easily mock the full callback here without monkeypatching, but redirect works
        print("-" * 50)

        # ---------------------------------------------------------
        # 7. Rate Limiting
        # ---------------------------------------------------------
        print("7. RATE LIMITING")
        # Test rate limiting by hammering a route
        codes = []
        for _ in range(15):
            codes.append(client.get("/health").status_code)
        print(f"   [Health endpoint 15 requests]: {codes[:5]} ... {codes[-3:]}")
        
        # Test rate limit on login
        login_codes = []
        for _ in range(15):
            login_codes.append(client.post("/auth/login", data={"username": "fake", "password": "fake"}).status_code)
        print(f"   [Login endpoint 15 requests]: {login_codes}")
        print("-" * 50)

        # ---------------------------------------------------------
        # 8. Security Headers
        # ---------------------------------------------------------
        print("8. SECURITY HEADERS")
        r = client.get("/health")
        print(f"   [X-Frame-Options]: {r.headers.get('x-frame-options')}")
        print(f"   [Strict-Transport-Security]: {r.headers.get('strict-transport-security')}")
        print(f"   [Content-Security-Policy]: {r.headers.get('content-security-policy')}")
        print("-" * 50)

        # ---------------------------------------------------------
        # 9. API Keys
        # ---------------------------------------------------------
        print("9. API KEYS")
        r = client.post("/api-keys/", json={"name": "test-key"}, headers=headers_a)
        print(f"   [Create Key]: {r.status_code}")
        if r.status_code == 201:
            key_id = r.json()["id"]
            raw_key = r.json()["key"]
            print(f"   [Raw Key Length]: {len(raw_key)}")
            
            r2 = client.delete(f"/api-keys/{key_id}", headers=headers_a)
            print(f"   [Revoke Key]: {r2.status_code}")
        print("-" * 50)

        # ---------------------------------------------------------
        # 10. Audit Logs
        # ---------------------------------------------------------
        print("10. AUDIT LOGS")
        logs = session.execute(select(AuditLog).order_by(AuditLog.at.desc()).limit(5)).scalars().all()
        for log_entry in logs:
            print(f"   [Audit]: {log_entry.action} by {log_entry.actor} (IP: {log_entry.ip_address})")
        print("-" * 50)

        # ---------------------------------------------------------
        # 11. Secret Retrieval
        # ---------------------------------------------------------
        print("11. SECRET ABSTRACTION")
        from app.security.secrets import get_secret_provider
        provider = get_secret_provider()
        enc = provider.encrypt("test-secret")
        dec = provider.decrypt_str(enc)
        print(f"   [Provider]: {provider.__class__.__name__}")
        print(f"   [Encrypted]: {enc[:15]}...")
        print(f"   [Decrypted == original]: {dec == 'test-secret'}")
        print("-" * 50)
        
        # Cleanup
        session.execute(AuditLog.__table__.delete().where(AuditLog.tenant_id.in_([tenant_a_id, tenant_b_id])))
        session.execute(ApiKey.__table__.delete().where(ApiKey.tenant_id.in_([tenant_a_id, tenant_b_id])))
        session.execute(Dashboard.__table__.delete().where(Dashboard.tenant_id.in_([tenant_a_id, tenant_b_id])))
        session.execute(DataSource.__table__.delete().where(DataSource.tenant_id.in_([tenant_a_id, tenant_b_id])))
        session.execute(User.__table__.delete().where(User.tenant_id.in_([tenant_a_id, tenant_b_id])))
        session.execute(Tenant.__table__.delete().where(Tenant.id.in_([tenant_a_id, tenant_b_id])))
        session.commit()
        print("CLEANUP COMPLETE.")

try:
    run_verifications()
except Exception as e:
    import traceback
    traceback.print_exc()
