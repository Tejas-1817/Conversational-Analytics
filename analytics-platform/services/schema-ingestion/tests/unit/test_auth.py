import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.models import User
from app.security.auth import get_password_hash
from app.db import get_session

client = TestClient(app)

@pytest.fixture
def mock_session():
    session = MagicMock()
    mock_user = User(id="12345678-1234-5678-1234-567812345678", email="admin@example.com", role="ADMIN", is_active=True, tenant_id="00000000-0000-0000-0000-000000000001")
    mock_user.password_hash = get_password_hash("admin")
    session.query.return_value.filter.return_value.first.return_value = mock_user
    return session

def test_auth_login_success(mock_session):
    app.dependency_overrides[get_session] = lambda: mock_session
    response = client.post("/auth/login", data={"username": "admin@example.com", "password": "admin"})
    assert response.status_code == 200
    assert "access_token" in response.json()
    app.dependency_overrides.clear()

def test_auth_login_failure(mock_session):
    app.dependency_overrides[get_session] = lambda: mock_session
    response = client.post("/auth/login", data={"username": "admin@example.com", "password": "wrong"})
    assert response.status_code in (400, 401)
    app.dependency_overrides.clear()

def test_auth_refresh(mock_session):
    # Mock token creation directly or just test failure path
    app.dependency_overrides[get_session] = lambda: mock_session
    response = client.post("/auth/refresh", json={"refresh_token": "bad_token"})
    assert response.status_code in (400, 401)
    app.dependency_overrides.clear()
