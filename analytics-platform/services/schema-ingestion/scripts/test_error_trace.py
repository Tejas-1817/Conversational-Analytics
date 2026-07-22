"""
Test to deliberately trigger a generic exception (not SQLSafetyError) and confirm
the trace ends with a status="error" entry for the active stage.
"""

import sys
import time
import json
import requests

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"c:\Users\Admin\Downloads\Analytics Tool\Analytics Tool\analytics-platform\services\schema-ingestion")

BASE = "http://localhost:8000"

def login():
    r = requests.post(f"{BASE}/auth/login",
                      data={"username": "admin@example.com", "password": "admin123"},
                      timeout=10)
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["access_token"]

def create_conversation(token):
    r = requests.post(f"{BASE}/engine/conversations",
                      headers={"Authorization": f"Bearer {token}"}, timeout=10)
    return r.json()["id"]

def send_query(token, conv_id, question):
    r = requests.post(f"{BASE}/engine/conversations/{conv_id}/query",
                      json={"message": question},
                      headers={"Authorization": f"Bearer {token}"}, timeout=30)
    return r.json()

def get_message(token, conv_id, msg_id):
    r = requests.get(f"{BASE}/engine/conversations/{conv_id}/messages/{msg_id}",
                     headers={"Authorization": f"Bearer {token}"}, timeout=10)
    return r.json()

def run():
    print("=== Testing generic exception trace ===")
    
    # 1. First, we need to inject a deliberate failure. We can query for a metric
    # that exists in the semantic layer but has no source column mapped to it,
    # which will cause the CompilerService to raise a ColumnResolutionError 
    # (a generic Exception from the perspective of chat_tasks).
    
    # Alternatively, querying something completely invalid might also trigger it, 
    # but let's query for "Total Revenue" after breaking its mapping.
    
    from app.db import session_scope
    from app.models import SemanticMetric
    
    with session_scope() as db:
        m = db.query(SemanticMetric).filter(SemanticMetric.name == "Total Revenue").first()
        if m:
            original_col = m.source_column_id
            m.source_column_id = None
            db.commit()
            print("✓ Injected fault: Broke 'Total Revenue' metric mapping")
        else:
            print("✗ Could not find metric to break")
            sys.exit(1)

    try:
        token = login()
        conv_id = create_conversation(token)
        print(f"✓ Created conversation")
        
        msg = send_query(token, conv_id, "Show total revenue by region")
        msg_id = msg["id"]
        print(f"✓ Job enqueued msg_id={msg_id}")
        
        while True:
            time.sleep(2)
            data = get_message(token, conv_id, msg_id)
            if data["status"] in ("complete", "error"):
                break
                
        print(f"✓ Terminal status reached: {data['status']}")
        
        trace = data.get("trace") or []
        print("\n--- Final Trace ---")
        print(json.dumps(trace, indent=2))
        
        assert data["status"] == "error", "Expected job to fail"
        assert trace, "Trace should not be empty"
        assert trace[-1]["status"] == "error", f"Last trace entry status should be 'error', got {trace[-1]['status']}"
        print("\n=== SUCCESS: Trace ended with explicit error entry ===")
        
    finally:
        # Restore mapping
        with session_scope() as db:
            m = db.query(SemanticMetric).filter(SemanticMetric.name == "Total Revenue").first()
            if m:
                m.source_column_id = original_col
                db.commit()
                print("\n✓ Fault reverted")

if __name__ == "__main__":
    run()
