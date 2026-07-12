"""Credential encryption round-trip and failure modes."""
import pytest

from app.security.crypto import decrypt_secret, encrypt_secret


def test_round_trip():
    assert decrypt_secret(encrypt_secret("s3cret-p@ss")) == "s3cret-p@ss"


def test_ciphertext_is_not_plaintext():
    assert b"s3cret" not in encrypt_secret("s3cret")


def test_missing_key_raises_actionable_error(monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("ENCRYPTION_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
        encrypt_secret("x")
