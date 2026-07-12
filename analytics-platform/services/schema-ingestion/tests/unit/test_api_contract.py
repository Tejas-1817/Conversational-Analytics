"""API contract guardrails — auth required, credentials never exposed."""
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import DataSourceOut, JobOut


def test_missing_api_key_is_rejected():
    client = TestClient(app)
    for path in ("/sources", "/jobs"):
        assert client.get(path).status_code == 401


def test_wrong_api_key_is_rejected():
    client = TestClient(app)
    assert client.get("/sources", headers={"X-API-Key": "wrong"}).status_code == 401


def test_no_response_model_exposes_credentials():
    banned = {"password", "credentials", "credentials_encrypted", "secret"}
    for model in (DataSourceOut, JobOut):
        leaked = banned & set(model.model_fields.keys())
        assert not leaked, f"{model.__name__} exposes {leaked}"


def test_health_endpoint_is_public():
    client = TestClient(app)
    assert client.get("/health").status_code == 200
