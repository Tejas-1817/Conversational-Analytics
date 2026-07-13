"""
API Key management for service accounts and machine integrations.

Keys are generated once and shown only at creation. After that, only
the bcrypt hash is stored. Keys can be scoped to specific permissions.

Key format: ak_{prefix}_{random_suffix}
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime
from typing import Optional, List

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.audit import audit, AuditEvent
from app.api.deps import require_admin, require_permission, Permission
from app.db import get_session
from app.models import ApiKey, User
from app.security.auth import get_password_hash

log = structlog.get_logger()
router = APIRouter(prefix="/api-keys", tags=["api-keys"])


def _generate_api_key() -> tuple[str, str, str]:
    """Generate (raw_key, prefix, hash). Raw key is shown once and never stored."""
    random_part = secrets.token_urlsafe(32)
    prefix = random_part[:8]
    raw_key = f"ak_{prefix}_{random_part}"
    key_hash = get_password_hash(raw_key)
    return raw_key, prefix, key_hash


# --- Schemas ---

class ApiKeyCreate(BaseModel):
    name: str
    scopes: List[str] = []
    expires_at: Optional[datetime] = None


class ApiKeyCreatedOut(BaseModel):
    id: uuid.UUID
    name: str
    key: str          # Raw key — shown ONCE only
    key_prefix: str
    scopes: List[str]
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ApiKeyOut(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    scopes: List[str]
    is_active: bool
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# --- Endpoints ---

@router.get("/", response_model=List[ApiKeyOut])
def list_api_keys(
    db: Session = Depends(get_session),
    user: User = Depends(require_permission(Permission.MANAGE_API_KEYS)),
):
    """List all active API keys for the calling user's tenant."""
    return (
        db.query(ApiKey)
        .filter(ApiKey.tenant_id == user.tenant_id)
        .order_by(ApiKey.created_at.desc())
        .all()
    )


@router.post("/", response_model=ApiKeyCreatedOut, status_code=201)
def create_api_key(
    body: ApiKeyCreate,
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(require_permission(Permission.MANAGE_API_KEYS)),
):
    """
    Create a new API key for the calling user's tenant.
    The raw key is returned ONCE and cannot be retrieved again.
    """
    # Check for duplicate name within tenant
    existing = (
        db.query(ApiKey)
        .filter(ApiKey.tenant_id == user.tenant_id, ApiKey.name == body.name)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="API key with this name already exists")

    raw_key, prefix, key_hash = _generate_api_key()

    api_key = ApiKey(
        tenant_id=user.tenant_id,
        user_id=user.id,
        name=body.name,
        key_hash=key_hash,
        key_prefix=prefix,
        scopes=body.scopes,
        expires_at=body.expires_at,
    )
    db.add(api_key)
    db.flush()

    audit(
        db,
        tenant_id=user.tenant_id,
        entity_type="api_keys",
        entity_id=api_key.id,
        action=AuditEvent.API_KEY_CREATED,
        actor=user.email,
        after={"name": body.name, "scopes": body.scopes, "prefix": prefix},
        request=request,
    )

    db.commit()
    db.refresh(api_key)
    log.info("api_key_created", name=body.name, tenant_id=str(user.tenant_id))

    # Return the raw key only at creation
    return ApiKeyCreatedOut(
        id=api_key.id,
        name=api_key.name,
        key=raw_key,
        key_prefix=api_key.key_prefix,
        scopes=api_key.scopes,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
    )


@router.delete("/{key_id}", status_code=200)
def revoke_api_key(
    key_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(require_permission(Permission.MANAGE_API_KEYS)),
):
    """Revoke (deactivate) an API key."""
    api_key = db.query(ApiKey).filter(
        ApiKey.id == key_id,
        ApiKey.tenant_id == user.tenant_id,
    ).first()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    api_key.is_active = False

    audit(
        db,
        tenant_id=user.tenant_id,
        entity_type="api_keys",
        entity_id=api_key.id,
        action=AuditEvent.API_KEY_REVOKED,
        actor=user.email,
        before={"name": api_key.name, "is_active": True},
        request=request,
    )

    db.commit()
    log.info("api_key_revoked", key_id=str(key_id), actor=user.email)
    return {"status": "revoked"}
