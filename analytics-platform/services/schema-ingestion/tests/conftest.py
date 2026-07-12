"""Shared fixtures. Unit tests must run with no DB, no network, no real secrets."""

import pytest
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def _test_settings(monkeypatch):
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("API_KEY", "test-key")
    # Clear the settings cache so env vars take effect per-test
    from app.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
