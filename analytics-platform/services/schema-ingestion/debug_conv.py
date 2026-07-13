import os
os.environ["ENCRYPTION_KEY"] = "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGs="
os.environ["LLM_PROVIDER"] = "mock"

from fastapi.testclient import TestClient
from app.main import app
from app.config import get_settings

client = TestClient(app)

# Login
res = client.post("/auth/login", data={"username": "admin@company.com", "password": "adminpassword123"})
assert res.status_code == 200, res.text
token = res.json()["access_token"]

# Create insight
try:
    insight_payload = {
        "name": "Revenue by Region 1234",
        "query": "Show me total revenue by region",
        "chart_config": {"chartType": None, "data": None}
    }
    res = client.post("/dashboards/insights", headers={"Authorization": f"Bearer {token}"}, json=insight_payload)
    print(res.status_code, res.text)
except Exception as e:
    import traceback
    traceback.print_exc()
