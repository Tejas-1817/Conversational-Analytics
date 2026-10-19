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
    "USER": {
        Permission.VIEW_SOURCES,
        Permission.MANAGE_SEMANTIC,
        Permission.VIEW_SEMANTIC,
        Permission.MANAGE_DASHBOARDS,
        Permission.VIEW_DASHBOARDS,
        Permission.SAVE_INSIGHTS,
        Permission.USE_AI_CHAT,
        Permission.EXPORT_DATA,
    },
    "ANALYST": {
        Permission.VIEW_SOURCES,
        Permission.MANAGE_SEMANTIC,
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

    try:
        user = session.query(User).filter(
            User.id == user_id,
            User.is_active == True,  # noqa: E712
        ).first()
    except Exception:
        user = None

    if user is None:
        from app.config import get_settings
        settings = get_settings()
        if str(user_id) == str(settings.default_tenant_id):
            return User(
                id=settings.default_tenant_id,
                tenant_id=settings.default_tenant_id,
                email=settings.admin_bootstrap_email,
                role="ADMIN",
                is_active=True
            )
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
    Platform admins have platform-wide authority.
    Raises 404 (not 403) to avoid leaking existence of resources to non-admins.
    """
    if current_user.role == "ADMIN":
        return
    if resource_tenant_id != current_user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )


def verify_user_has_source_access(session: Session, current_user: User, source_id: uuid.UUID) -> None:
    """
    Assert that the user has been granted access to this data source, or is an ADMIN.
    Raises 403 Forbidden if not authorized.
    """
    if current_user.role == "ADMIN":
        return
    from app.models import UserDataSourceAccess
    from sqlalchemy import select
    grant = session.scalar(
        select(UserDataSourceAccess).where(
            UserDataSourceAccess.tenant_id == current_user.tenant_id,
            UserDataSourceAccess.user_id == current_user.id,
            UserDataSourceAccess.source_id == source_id,
        )
    )
    if not grant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this data source."
        )


def verify_domain_ownership(current_user: User, domain: Any) -> None:
    """
    Enforce strict user-level domain privacy.
    A domain is private to its creator. Even within the same enterprise, other users cannot access it.
    Raises 404 Not Found (anti-enumeration defense).
    """
    if current_user.role == "ADMIN":
        return

    if getattr(domain, "user_id", None) is not None:
        if domain.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Domain not found"
            )
    else:
        # Legacy domain fallback: check created_by email
        if domain.created_by != current_user.email:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Domain not found"
            )


def verify_user_has_domain_access(session: Session, current_user: User, domain: Any) -> None:
    """
    Assert that the user has permission to access this domain.
    1. ADMIN users have unrestricted access.
    2. Creator ownership is strictly enforced (raises 404 for non-owners).
    3. User must have access to the domain's data source (raises 404 to prevent enumeration).
    """
    if current_user.role == "ADMIN":
        return

    # 1. Enforce creator privacy (anti-enumeration)
    verify_domain_ownership(current_user, domain)

    from app.models import UserDataSourceAccess, DomainTable, TableMeta
    from sqlalchemy import select

    # If the user has not been granted access to any data source at all, they cannot access any domain
    has_any_grant = session.scalar(
        select(UserDataSourceAccess.id).where(
            UserDataSourceAccess.tenant_id == current_user.tenant_id,
            UserDataSourceAccess.user_id == current_user.id,
        )
    )
    if not has_any_grant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Domain not found"
        )

    if domain.source_id is not None:
        try:
            verify_user_has_source_access(session, current_user, domain.source_id)
        except HTTPException:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Domain not found"
            )
    else:
        table_sources = (
            session.query(TableMeta.source_id)
            .join(DomainTable, DomainTable.table_id == TableMeta.id)
            .filter(DomainTable.domain_id == domain.id)
            .distinct()
            .all()
        )
        if not table_sources:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Domain not found"
            )
        for (src_id,) in table_sources:
            if src_id:
                try:
                    verify_user_has_source_access(session, current_user, src_id)
                except HTTPException:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Domain not found"
                    )


def require_user(current_user: User = Depends(get_current_user)) -> User:
    """Any authenticated active user (ADMIN or USER)."""
    return current_user


def get_user_permitted_table_ids(session: Session, current_user: User, source_id: uuid.UUID) -> set[uuid.UUID]:
    """
    Return the set of TableMeta IDs that the user is permitted to access for the given source_id.
    - ADMIN users: All tables of the data source.
    - Non-admin users: Only tables explicitly granted in user_table_access.
    """
    from app.models import TableMeta, UserTableAccess
    if current_user.role == "ADMIN":
        tables = session.query(TableMeta.id).filter(TableMeta.source_id == source_id).all()
        return {t[0] for t in tables}

    grants = session.query(UserTableAccess.table_id).filter(
        UserTableAccess.tenant_id == current_user.tenant_id,
        UserTableAccess.user_id == current_user.id,
        UserTableAccess.source_id == source_id,
    ).all()
    return {g[0] for g in grants}


def verify_user_has_table_access(session: Session, current_user: User, source_id: uuid.UUID, table_id: uuid.UUID) -> None:
    """
    Assert that the user has been granted access to this specific table.
    Deny-by-default for ordinary users. Raises 403 Forbidden if not authorized.
    """
    if current_user.role == "ADMIN":
        return

    # First verify parent data source grant
    verify_user_has_source_access(session, current_user, source_id)

    from app.models import UserTableAccess
    from sqlalchemy import select
    grant = session.scalar(
        select(UserTableAccess.id).where(
            UserTableAccess.tenant_id == current_user.tenant_id,
            UserTableAccess.user_id == current_user.id,
            UserTableAccess.source_id == source_id,
            UserTableAccess.table_id == table_id,
        )
    )
    if not grant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this table."
        )


