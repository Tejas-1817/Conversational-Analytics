"""
Tenant administration API (super-admin only).

Allows platform operators to:
  - List all tenants
  - Create a new tenant (onboarding)
  - Suspend / reactivate a tenant
  - Get tenant details

These endpoints require role=ADMIN AND membership in the default tenant
(i.e., the platform super-admin tenant).
"""
from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.audit import audit
from app.db import get_session
from app.models import Tenant, TenantPolicy, User

log = structlog.get_logger()
router = APIRouter(prefix="/tenants", tags=["tenants"])

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def _require_super_admin(current_user: User = Depends(require_admin)) -> User:
    """Ensure the caller is an ADMIN (platform administrator)."""
    return current_user


# --- Schemas ---

class TenantCreate(BaseModel):
    name: str
    slug: str
    display_name: str | None = None
    plan: str = "starter"
    max_users: int = 10
    max_sources: int = 5


class TenantUpdate(BaseModel):
    name: str | None = None
    display_name: str | None = None
    plan: str | None = None
    max_users: int | None = None
    max_sources: int | None = None


class TenantOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    display_name: str | None
    plan: str
    is_active: bool
    max_users: int
    max_sources: int
    created_at: datetime

    class Config:
        from_attributes = True


class TenantUserOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime
    tenant_id: uuid.UUID

    class Config:
        from_attributes = True


class TenantPolicyOut(BaseModel):
    tenant_id: uuid.UUID
    rate_chat_per_min: int
    rate_login_per_min: int
    rate_export_per_min: int
    max_query_rows: int
    query_timeout_ms: int
    allow_raw_sql: bool
    require_mfa: bool
    session_timeout_min: int

    class Config:
        from_attributes = True


class TenantPolicyUpdate(BaseModel):
    rate_chat_per_min: int | None = None
    rate_login_per_min: int | None = None
    max_query_rows: int | None = None
    allow_raw_sql: bool | None = None
    require_mfa: bool | None = None
    session_timeout_min: int | None = None


# --- Endpoints ---

@router.get("", response_model=list[TenantOut])
@router.get("/", response_model=list[TenantOut], include_in_schema=False)
def list_tenants(
    db: Session = Depends(get_session),
    _: User = Depends(_require_super_admin),
):
    """List all tenants (super-admin only)."""
    return db.query(Tenant).order_by(Tenant.created_at.desc()).all()


@router.post("", response_model=TenantOut, status_code=201)
@router.post("/", response_model=TenantOut, status_code=201, include_in_schema=False)
def create_tenant(
    body: TenantCreate,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(_require_super_admin),
):
    """Onboard a new tenant / organization (super-admin only)."""
    existing = db.query(Tenant).filter(
        (Tenant.name == body.name) | (Tenant.slug == body.slug)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Tenant name or slug already exists")

    tenant = Tenant(
        name=body.name,
        slug=body.slug,
        display_name=body.display_name,
        plan=body.plan,
        max_users=body.max_users,
        max_sources=body.max_sources,
        created_by=admin.email,
    )
    db.add(tenant)
    db.flush()

    # Create default policy for the tenant
    db.add(TenantPolicy(tenant_id=tenant.id))

    audit(
        db,
        tenant_id=admin.tenant_id,
        entity_type="tenants",
        entity_id=tenant.id,
        action="TENANT_CREATED",
        actor=admin.email,
        after={"name": body.name, "slug": body.slug, "plan": body.plan},
        request=request,
    )

    db.commit()
    db.refresh(tenant)
    log.info("tenant_created", name=body.name, slug=body.slug)
    return tenant


@router.get("/{tenant_id}", response_model=TenantOut)
def get_tenant(
    tenant_id: uuid.UUID,
    db: Session = Depends(get_session),
    _: User = Depends(_require_super_admin),
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.patch("/{tenant_id}", response_model=TenantOut)
def update_tenant(
    tenant_id: uuid.UUID,
    body: TenantUpdate,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(_require_super_admin),
):
    """Update tenant metadata (display name, plan, limits)."""
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    before_data = {"name": tenant.name, "display_name": tenant.display_name, "plan": tenant.plan}
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(tenant, field, value)

    audit(
        db,
        tenant_id=admin.tenant_id,
        entity_type="tenants",
        entity_id=tenant.id,
        action="TENANT_UPDATED",
        actor=admin.email,
        before=before_data,
        after=body.model_dump(exclude_none=True),
        request=request,
    )
    db.commit()
    db.refresh(tenant)
    return tenant


@router.get("/{tenant_id}/users", response_model=list[TenantUserOut])
def list_tenant_users(
    tenant_id: uuid.UUID,
    db: Session = Depends(get_session),
    _: User = Depends(_require_super_admin),
):
    """List all users belonging to a specific enterprise."""
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return db.query(User).filter(User.tenant_id == tenant_id).order_by(User.created_at.desc()).all()


@router.post("/{tenant_id}/suspend", response_model=TenantOut)
def suspend_tenant(
    tenant_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(_require_super_admin),
):
    """Suspend a tenant — all their users will be blocked from logging in."""
    if str(tenant_id) == DEFAULT_TENANT_ID:
        raise HTTPException(status_code=400, detail="Cannot suspend the platform admin tenant")

    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant.is_active = False
    audit(db, tenant_id=admin.tenant_id, entity_type="tenants", entity_id=tenant.id,
          action="TENANT_SUSPENDED", actor=admin.email, request=request)
    db.commit()
    db.refresh(tenant)
    log.info("tenant_suspended", tenant_id=str(tenant_id))
    return tenant


@router.post("/{tenant_id}/reactivate", response_model=TenantOut)
def reactivate_tenant(
    tenant_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(_require_super_admin),
):
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant.is_active = True
    audit(db, tenant_id=admin.tenant_id, entity_type="tenants", entity_id=tenant.id,
          action="TENANT_REACTIVATED", actor=admin.email, request=request)
    db.commit()
    db.refresh(tenant)
    return tenant


@router.get("/{tenant_id}/policy", response_model=TenantPolicyOut)
def get_tenant_policy(
    tenant_id: uuid.UUID,
    db: Session = Depends(get_session),
    _: User = Depends(_require_super_admin),
):
    policy = db.get(TenantPolicy, tenant_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Tenant policy not found")
    return policy


@router.patch("/{tenant_id}/policy", response_model=TenantPolicyOut)
def update_tenant_policy(
    tenant_id: uuid.UUID,
    body: TenantPolicyUpdate,
    db: Session = Depends(get_session),
    _: User = Depends(_require_super_admin),
):
    policy = db.get(TenantPolicy, tenant_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Tenant policy not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(policy, field, value)

    db.commit()
    db.refresh(policy)
    return policy
