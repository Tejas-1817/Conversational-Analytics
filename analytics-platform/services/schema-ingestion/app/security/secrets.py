"""
Pluggable Secret Provider abstraction.

Supported backends:
  - FernetEnvProvider  (default, uses ENCRYPTION_KEY env var — no extra infra)
  - VaultProvider      (HashiCorp Vault KV v2 — set SECRET_BACKEND=vault)

Switch backends via SECRET_BACKEND env var. No code change required.
"""
from __future__ import annotations

import abc
import base64
import hashlib
import os
from typing import TYPE_CHECKING

import structlog

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class SecretProvider(abc.ABC):
    """Common interface for all secret backends."""

    @abc.abstractmethod
    def encrypt(self, plaintext: str | bytes) -> bytes:
        """Encrypt a secret and return ciphertext bytes."""

    @abc.abstractmethod
    def decrypt(self, ciphertext: bytes) -> bytes:
        """Decrypt ciphertext bytes and return plaintext bytes."""

    def encrypt_str(self, plaintext: str) -> bytes:
        return self.encrypt(plaintext.encode("utf-8"))

    def decrypt_str(self, ciphertext: bytes) -> str:
        return self.decrypt(ciphertext).decode("utf-8")


# ---------------------------------------------------------------------------
# Backend 1: Fernet (env-based, current default)
# ---------------------------------------------------------------------------

class FernetEnvProvider(SecretProvider):
    """
    Uses a Fernet key stored in the ENCRYPTION_KEY environment variable.
    This is the default backend — identical to the pre-Phase-6 behavior.
    """

    def __init__(self) -> None:
        from cryptography.fernet import Fernet
        from app.config import get_settings

        key = get_settings().encryption_key
        if not key:
            raise RuntimeError(
                "ENCRYPTION_KEY is not set. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, plaintext: str | bytes) -> bytes:
        data = plaintext.encode("utf-8") if isinstance(plaintext, str) else plaintext
        return self._fernet.encrypt(data)

    def decrypt(self, ciphertext: bytes) -> bytes:
        return self._fernet.decrypt(ciphertext)


# ---------------------------------------------------------------------------
# Backend 2: HashiCorp Vault KV v2 (stub — ready for production wiring)
# ---------------------------------------------------------------------------

class VaultProvider(SecretProvider):
    """
    Wraps HashiCorp Vault KV v2.
    Requires: VAULT_ADDR, VAULT_TOKEN, VAULT_MOUNT env vars.

    NOTE: This implementation uses AES-256-GCM locally for encrypt/decrypt and
    stores the key material in Vault. Set SECRET_BACKEND=vault to activate.
    """

    _VAULT_SECRET_PATH = "analytics-platform/encryption-key"

    def __init__(self) -> None:
        from app.config import get_settings
        import urllib.request
        import json

        settings = get_settings()
        self._vault_addr = settings.vault_addr
        self._vault_token = settings.vault_token
        self._vault_mount = settings.vault_mount

        # Fetch or create the AES key from Vault
        key_b64 = self._fetch_or_create_key()
        self._key = base64.b64decode(key_b64)

    def _vault_request(self, method: str, path: str, body: dict | None = None) -> dict:
        import urllib.request, urllib.error, json
        url = f"{self._vault_addr}/v1/{self._vault_mount}/data/{path}"
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"X-Vault-Token": self._vault_token,
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {}
            raise

    def _fetch_or_create_key(self) -> str:
        result = self._vault_request("GET", self._VAULT_SECRET_PATH)
        if result and result.get("data", {}).get("data", {}).get("key"):
            return result["data"]["data"]["key"]
        # Generate a new AES-256 key and store it
        key = base64.b64encode(os.urandom(32)).decode()
        self._vault_request("POST", self._VAULT_SECRET_PATH, {"data": {"key": key}})
        log.info("vault_encryption_key_created", path=self._VAULT_SECRET_PATH)
        return key

    def encrypt(self, plaintext: str | bytes) -> bytes:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        data = plaintext.encode("utf-8") if isinstance(plaintext, str) else plaintext
        nonce = os.urandom(12)
        ciphertext = AESGCM(self._key).encrypt(nonce, data, None)
        return nonce + ciphertext  # prepend nonce

    def decrypt(self, ciphertext: bytes) -> bytes:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce, ct = ciphertext[:12], ciphertext[12:]
        return AESGCM(self._key).decrypt(nonce, ct, None)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_provider: SecretProvider | None = None


def get_secret_provider() -> SecretProvider:
    """Return the configured SecretProvider singleton."""
    global _provider
    if _provider is None:
        from app.config import get_settings
        backend = get_settings().secret_backend
        if backend == "vault":
            log.info("secret_backend_vault")
            _provider = VaultProvider()
        else:
            log.info("secret_backend_fernet_env")
            _provider = FernetEnvProvider()
    return _provider


# ---------------------------------------------------------------------------
# Convenience helpers (drop-in replacements for old encrypt_secret / decrypt_secret)
# ---------------------------------------------------------------------------

def encrypt_secret(plaintext: str | bytes) -> bytes:
    return get_secret_provider().encrypt(plaintext)


def decrypt_secret(ciphertext: bytes) -> str:
    return get_secret_provider().decrypt_str(ciphertext)
