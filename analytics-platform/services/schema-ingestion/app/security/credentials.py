"""Database credential models and storage interfaces."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol

CREDENTIAL_SECRET_REF_TEMPLATE = (
    "tenants/{tenant_id}/data-sources/{source_id}/credentials"
)


def build_credential_secret_ref(
    tenant_id: uuid.UUID,
    source_id: uuid.UUID,
) -> str:
    """Build the tenant-isolated secret reference for a data source."""

    return CREDENTIAL_SECRET_REF_TEMPLATE.format(
        tenant_id=tenant_id,
        source_id=source_id,
    )

@dataclass(frozen=True, slots=True)
class DatabaseCredentials:
    """Decrypted credentials for connecting to a customer database."""

    username: str
    password: str = field(repr=False)
    ca_certificate: str | None = None
    client_certificate: str | None = None
    client_private_key: str | None = field(
        default=None,
        repr=False,
    )


class CredentialStore(Protocol):
    """Storage interface for customer database credentials."""

    def put(
        self,
        *,
        tenant_id: uuid.UUID,
        source_id: uuid.UUID,
        credentials: DatabaseCredentials,
    ) -> str:
        """Store credentials and return an opaque secret reference."""
        ...

    def get(
        self,
        secret_ref: str,
    ) -> DatabaseCredentials:
        """Retrieve credentials using an opaque secret reference."""
        ...

    def delete(
        self,
        secret_ref: str,
    ) -> None:
        """Delete credentials associated with a secret reference."""
        ...