"""
Credential encryption — now routes through the pluggable SecretProvider.

Backwards-compatible: all existing callers of encrypt_secret / decrypt_secret
continue to work unchanged. The backend (Fernet env vs Vault) is selected via
the SECRET_BACKEND environment variable.
"""
from app.security.secrets import encrypt_secret, decrypt_secret

__all__ = ["encrypt_secret", "decrypt_secret"]
