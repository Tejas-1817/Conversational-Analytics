"""
Shared API dependencies.

Provides:
  - get_current_user(): JWT validation + user lookup
  - require_admin() / require_analyst() / require_viewer(): Role gates
  - require_permission(perm): Granular permission factory
  - get_tenant(): Active tenant lookup + validation
  - verify_tenant_resource(): Asserts a resource belongs to the calling tenant

Phase 6 additions:
  - Granular permission model
  - Tenant validation dependency
  - Cross-tenant access protection
"""
from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Tenant, User
from app.security.auth import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

# ---------------------------------------------------------------------------
# Granular permission constants
# ---------------------------------------------------------------------------

class Permission:
    # User management
    MANAGE_USERS = "manage_users"
    VIEW_USERS = "view_users"

    # Tenant administration
    MANAGE_TENANTS = "manage_tenants"

    # Data Sources
    MANAGE_SOURCES = "manage_sources"
    VIEW_SOURCES = "view_sources"

    # Semantic Layer
    MANAGE_SEMANTIC = "manage_semantic"
    VIEW_SEMANTIC = "view_semantic"

    # Ingestion
    TRIGGER_INGESTION = "trigger_ingestion"
    VIEW_JOBS = "view_jobs"

    # Dashboards & Insights
    MANAGE_DASHBOARDS = "manage_dashboards"
    VIEW_DASHBOARDS = "view_dashboards"
    SAVE_INSIGHTS = "save_insights"

    # AI Chat
    USE_AI_CHAT = "use_ai_chat"

    # Exports
    EXPORT_DATA = "export_data"

    # Audit
    VIEW_AUDIT_LOG = "view_audit_log"

    # API Keys
    MANAGE_API_KEYS = "manage_api_keys"


# RBAC permission matrix
_ROLE_PERMISSIONS: dict[str, set[str]] = {
    "ADMIN": {
        Permission.MANAGE_USERS,
        Permission.VIEW_USERS,
        Permission.MANAGE_TENANTS,
        Permission.MANAGE_SOURCES,
        Permission.VIEW_SOURCES,
        Permission.MANAGE_SEMANTIC,
        Permission.VIEW_SEMANTIC,
        Permission.TRIGGER_INGESTION,
        Permission.VIEW_JOBS,
        Permission.MANAGE_DASHBOARDS,
        Permission.VIEW_DASHBOARDS,
        Permission.SAVE_INSIGHTS,
        Permission.USE_AI_CHAT,
        Permission.EXPORT_DATA,
        Permission.VIEW_AUDIT_LOG,
        Permission.MANAGE_API_KEYS,
    },
    "ANALYST": {
        Permission.VIEW_SOURCES,
        Permission.VIEW_SEMANTIC,
        Permission.VIEW_JOBS,
        Permission.MANAGE_DASHBOARDS,
        Permission.VIEW_DASHBOARDS,
        Permission.SAVE_INSIGHTS,
        Permission.USE_AI_CHAT,
        Permission.EXPORT_DATA,
        Permission.VIEW_USERS,
    },
    "VIEWER": {
        Permission.VIEW_SOURCES,
        Permission.VIEW_SEMANTIC,
        Permission.VIEW_DASHBOARDS,
        Permission.USE_AI_CHAT,
    },
}


def has_permission(role: str, permission: str) -> bool:
    return permission in _ROLE_PERMISSIONS.get(role, set())


# ---------------------------------------------------------------------------
# Core dependencies
# ---------------------------------------------------------------------------

def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    user = session.query(User).filter(
        User.id == user_id,
        User.is_active == True,  # noqa: E712
    ).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


def get_tenant(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Tenant:
    """Validate that the calling user's tenant exists and is active."""
    tenant = session.query(Tenant).filter(
        Tenant.id == current_user.tenant_id,
        Tenant.is_active == True,  # noqa: E712
    ).first()
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant not found or suspended",
        )
    return tenant


# ---------------------------------------------------------------------------
# Role-based shortcuts
# ---------------------------------------------------------------------------

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def require_analyst(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("ADMIN", "ANALYST"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Analyst or Admin access required",
        )
    return current_user


def require_viewer(current_user: User = Depends(get_current_user)) -> User:
    # Any active authenticated user has viewer access at minimum
    return current_user


# ---------------------------------------------------------------------------
# Granular permission factory
# ---------------------------------------------------------------------------

def require_permission(permission: str) -> Callable:
    """
    FastAPI dependency factory for granular permission checks.

    Usage:
        @router.get("/sensitive")
        def endpoint(user: User = Depends(require_permission(Permission.EXPORT_DATA))):
            ...
    """
    def _check(current_user: User = Depends(get_current_user)) -> User:
        if not has_permission(current_user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission}",
            )
        return current_user
    return _check


# ---------------------------------------------------------------------------
# Tenant resource ownership validation
# ---------------------------------------------------------------------------

def verify_tenant_owns(resource_tenant_id: uuid.UUID, current_user: User) -> None:
    """
    Assert that a resource belongs to the calling user's tenant.
    Raises 404 (not 403) to avoid leaking existence of resources.
    """
    if resource_tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )
