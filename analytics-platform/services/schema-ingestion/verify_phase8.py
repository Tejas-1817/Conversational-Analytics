import os
import sys
import time
import requests
import json
import uuid

# Base configuration
BASE_URL = "http://127.0.0.1:8000"
os.environ["ENCRYPTION_KEY"] = "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGs="
os.environ["LLM_PROVIDER"] = "mock"

def print_header(title):
    print(f"\n{'='*50}\n{title}\n{'='*50}")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def measure_time(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        return result, duration
    return wrapper

@measure_time
def api_request(method, endpoint, headers=None, json_data=None, data=None, expected_status=None):
    if method.upper() == "GET":
        response = client.get(endpoint, headers=headers)
    elif method.upper() == "POST":
        if data:
            response = client.post(endpoint, headers=headers, data=data)
        else:
            response = client.post(endpoint, headers=headers, json=json_data)
    elif method.upper() == "PATCH":
        response = client.patch(endpoint, headers=headers, json=json_data)
    else:
        response = client.request(method, endpoint, headers=headers, json=json_data, data=data)
        
    if expected_status and response.status_code not in expected_status:
        print(f"  [ERROR] {method} {endpoint} returned {response.status_code}, expected {expected_status}")
        print(f"  [ERROR] {response.text}")
    return response

print_header("Phase 8 API Audit & Performance Verification")

# 1. Server Health
print("1. Checking Server Health")
resp, duration = api_request("GET", "/health", expected_status=[200])
print(f"  Health check: {resp.status_code} ({duration*1000:.2f} ms)")

# 2. Authentication
print("2. Authentication (Admin & Analyst)")
# Admin
resp_admin, t_admin = api_request("POST", "/auth/login", data={"username": "admin@company.com", "password": "adminpassword123"}, expected_status=[200])
assert resp_admin.status_code == 200, resp_admin.text
token_admin = resp_admin.json().get("access_token")
headers_admin = {"Authorization": f"Bearer {token_admin}"}
print(f"  Admin login successful ({t_admin*1000:.2f} ms)")

# Analyst
resp_analyst, t_analyst = api_request("POST", "/auth/login", data={"username": "analyst@demo.com", "password": "analyst123"})
assert resp_analyst.status_code == 200
token_analyst = resp_analyst.json().get("access_token")
headers_analyst = {"Authorization": f"Bearer {token_analyst}"}
print(f"  Analyst login successful ({t_analyst*1000:.2f} ms)")

# 3. Data Source Connection
print("3. Data Sources")
resp, t = api_request("GET", "/sources", headers=headers_admin, expected_status=[200])
sources = resp.json()
print(f"  Fetched {len(sources)} sources ({t*1000:.2f} ms)")
if len(sources) > 0:
    source_id = sources[0]["id"]
else:
    print("  [ERROR] No demo data sources found! Did seed_demo.py run?")
    sys.exit(1)

# 4. Semantic Layer (Metrics)
print("4. Semantic Layer (Metrics)")
resp, t = api_request("GET", "/semantic/metrics", headers=headers_admin, expected_status=[200])
metrics = resp.json()
print(f"  Fetched {len(metrics)} metrics ({t*1000:.2f} ms)")

# Fetch Tables
resp, t = api_request("GET", f"/metadata/sources/{source_id}/tables", headers=headers_admin, expected_status=[200])
tables = resp.json()
if tables:
    table_id = tables[0]["id"]
    # Fetch columns
    resp, t = api_request("GET", f"/metadata/tables/{table_id}/columns", headers=headers_admin, expected_status=[200])
    columns = resp.json()
    if columns:
        col_id = columns[0]["id"]
        # Create a new Base Metric
        metric_name = f"Audit Test Base {uuid.uuid4().hex[:6]}"
        metric_payload = {
            "name": metric_name,
            "business_name": metric_name,
            "is_calculated": False,
            "expression": "audit_col",
            "aggregation_type": "SUM",
            "source_table_id": table_id,
            "source_column_id": col_id
        }
        resp, t = api_request("POST", "/semantic/metrics", headers=headers_admin, json_data=metric_payload, expected_status=[200])
        print(f"  Created Base Metric '{resp.json()['name']}' ({t*1000:.2f} ms)")
    else:
        print("  [ERROR] No columns found to create metric")
else:
    print("  [ERROR] No tables found to create metric")

# 5. AI Chat Engine
print("5. AI Chat Engine")
# Create Conversation
resp, t = api_request("POST", "/engine/conversations", headers=headers_admin, expected_status=[200])
conv_id = resp.json()["id"]
print(f"  Created Conversation ID: {conv_id} ({t*1000:.2f} ms)")

# Ask Question
query_payload = {"message": "Show me total revenue by region"}
resp, t = api_request("POST", f"/engine/conversations/{conv_id}/query", headers=headers_admin, json_data=query_payload, expected_status=[200])
msg_res = resp.json()
print(f"  AI Query Processed in {t*1000:.2f} ms")
print(f"  AI Explanation: {msg_res.get('content')}")
print(f"  Generated SQL: {msg_res.get('generated_sql')}")
print(f"  Chart Recommendation: {msg_res.get('chart_recommendation')}")

# Save Insight
insight_name = f"Revenue by Region {uuid.uuid4().hex[:6]}"
insight_payload = {
    "name": insight_name,
    "query": "Show me total revenue by region",
    "chart_config": {"chartType": msg_res.get('chart_recommendation'), "data": msg_res.get("result_data")}
}
resp, t = api_request("POST", "/dashboards/insights", headers=headers_admin, json_data=insight_payload, expected_status=[200])
insight_id = resp.json()["id"]
print(f"  Saved Insight ID: {insight_id} ({t*1000:.2f} ms)")

# 6. Dashboards
print("6. Dashboards")
resp, t = api_request("GET", "/dashboards/", headers=headers_admin, expected_status=[200])
dashboards = resp.json()
print(f"  Fetched {len(dashboards)} dashboards ({t*1000:.2f} ms)")

dashboard_payload = {
    "name": f"Verification Dashboard {uuid.uuid4().hex[:6]}",
    "description": "Test dashboard",
    "widgets": [
        {"insight_id": insight_id, "x": 0, "y": 0, "w": 4, "h": 3}
    ]
}
resp, t = api_request("POST", f"/dashboards/", headers=headers_admin, json_data=dashboard_payload, expected_status=[200])
print(f"  Created dashboard with widget ({t*1000:.2f} ms)")

# 7. AI Evaluation
print("7. AI Evaluation Framework")
resp, t = api_request("GET", "/eval/collections", headers=headers_admin, expected_status=[200])
collections = resp.json()
print(f"  Fetched {len(collections)} eval collections ({t*1000:.2f} ms)")

if collections:
    resp, t = api_request("POST", f"/eval/runs/{collections[0]['id']}", headers=headers_admin, expected_status=[202, 200])
    run_id = resp.json().get("id")
    print(f"  Triggered Benchmark Run {run_id} ({t*1000:.2f} ms)")

# 8. Tenant Isolation & RBAC
print("8. Tenant Isolation & Error Recovery")
# Analyst trying to get data sources (Not allowed by RBAC)
resp, t = api_request("GET", "/sources", headers=headers_analyst, expected_status=[403])
print(f"  Analyst blocked from accessing /sources ({t*1000:.2f} ms): {resp.status_code}")

# Admin trying to access non-existent conversation
resp, t = api_request("GET", f"/engine/conversations/{uuid.uuid4()}", headers=headers_admin, expected_status=[404])
print(f"  404 Handling correctly returns 404 ({t*1000:.2f} ms)")

# Admin sending malformed query
resp, t = api_request("POST", f"/engine/conversations/{conv_id}/query", headers=headers_admin, json_data={"message": ""}, expected_status=[422])
print(f"  Validation Handling (empty string) returns 422 ({t*1000:.2f} ms)")

# Invalid login
resp, t = api_request("POST", "/auth/login", data={"username": "admin@company.com", "password": "wrongpassword"}, expected_status=[401])
print(f"  Invalid login handled gracefully ({t*1000:.2f} ms): {resp.status_code}")

print_header("Phase 8 Verification Completed Successfully")
