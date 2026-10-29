"""User management — fully tenant-scoped with audit logging."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.deps import Permission, require_admin, require_permission
from app.audit import AuditEvent, audit
from app.db import get_session
from app.models import DataSource, TableMeta, Tenant, User, UserDataSourceAccess, UserTableAccess
from app.schemas import (
    UserDataSourceAccessUpdate,
    UserDataSourceItemOut,
    UserTableAccessItemOut,
    UserTableAccessUpdate,
)
from app.security.auth import get_password_hash

router = APIRouter(prefix="/users", tags=["users"])


# --- Schemas ---

class UserCreate(BaseModel):
    email: str
    password: str
    role: str = "USER"
    tenant_id: uuid.UUID | None = None


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime
    tenant_id: uuid.UUID | None = None
    granted_sources_count: int | None = None

    class Config:
        from_attributes = True


class UserRoleUpdate(BaseModel):
    role: str


class UserEnterpriseUpdate(BaseModel):
    tenant_id: uuid.UUID


class ResetPasswordRequest(BaseModel):
    new_password: str


class UserStatusUpdate(BaseModel):
    is_active: bool


def _get_target_user(user_id: uuid.UUID, db: Session, admin: User) -> User:
    """Helper to retrieve user and verify admin has authority over the target user."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if admin.role != "ADMIN" and user.tenant_id != admin.tenant_id:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# --- Endpoints ---

@router.get("", response_model=list[UserOut])
def get_users(
    tenant_id: uuid.UUID | None = None,
    db: Session = Depends(get_session),
    admin: User = Depends(require_permission(Permission.VIEW_USERS)),
):
    """List users scoped strictly to the calling user's tenant or filtered by tenant_id for platform admins."""
    query = select(User)
    if admin.role == "ADMIN":
        if tenant_id is not None:
            query = query.where(User.tenant_id == tenant_id)
    else:
        query = query.where(User.tenant_id == admin.tenant_id)
    users = db.scalars(query.order_by(User.created_at.desc())).all()

    grants = db.execute(
        select(UserDataSourceAccess.user_id, func.count(UserDataSourceAccess.source_id))
        .group_by(UserDataSourceAccess.user_id)
    ).all()
    grant_counts = {u_id: count for u_id, count in grants}

    result = []
    for u in users:
        total_tenant_sources = db.scalar(
            select(func.count(DataSource.id)).where(DataSource.tenant_id == u.tenant_id)
        ) or 0
        u_dict = {
            "id": u.id,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "tenant_id": u.tenant_id,
            "created_at": u.created_at,
            "granted_sources_count": total_tenant_sources if u.role == "ADMIN" else grant_counts.get(u.id, 0),
        }
        result.append(UserOut(**u_dict))
    return result


@router.post("", response_model=UserOut, status_code=201)
def invite_user(
    user_in: UserCreate,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(require_admin),
):
    normalized_role = user_in.role.upper()
    if normalized_role in ("ANALYST", "VIEWER"):
        normalized_role = "USER"
    if normalized_role not in ("ADMIN", "USER"):
        raise HTTPException(status_code=400, detail=f"Invalid role: {user_in.role}")

    target_tenant_id = user_in.tenant_id if (user_in.tenant_id and admin.role == "ADMIN") else admin.tenant_id
    target_tenant = db.get(Tenant, target_tenant_id)
    if not target_tenant:
        raise HTTPException(status_code=400, detail="Target enterprise not found")

    existing = db.scalar(
        select(User).where(User.tenant_id == target_tenant_id, User.email == user_in.email)
    )
    if existing:
        raise HTTPException(status_code=400, detail="User already exists in this enterprise")

    db_obj = User(
        tenant_id=target_tenant_id,
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        role=normalized_role,
    )
    db.add(db_obj)
    db.flush()

    audit(
        db,
        tenant_id=target_tenant_id,
        entity_type="users",
        entity_id=db_obj.id,
        action=AuditEvent.USER_CREATED,
        actor=admin.email,
        after={"email": user_in.email, "role": normalized_role, "tenant_id": str(target_tenant_id)},
        request=request,
    )

    db.commit()
    db.refresh(db_obj)
    return db_obj


@router.patch("/{user_id}/role", response_model=UserOut)
def update_user_role(
    user_id: uuid.UUID,
    body: UserRoleUpdate,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(require_admin),
):
    """Change a user's role. Allowed for platform admins or admins in the same tenant."""
    normalized_role = body.role.upper()
    if normalized_role in ("ANALYST", "VIEWER"):
        normalized_role = "USER"
    if normalized_role not in ("ADMIN", "USER"):
        raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")

    user = _get_target_user(user_id, db, admin)
    old_role = user.role
    user.role = normalized_role

    audit(
        db,
        tenant_id=user.tenant_id,
        entity_type="users",
        entity_id=user.id,
        action=AuditEvent.USER_ROLE_CHANGED,
        actor=admin.email,
        before={"role": old_role},
        after={"role": normalized_role},
        request=request,
    )

    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/enterprise", response_model=UserOut)
def update_user_enterprise(
    user_id: uuid.UUID,
    body: UserEnterpriseUpdate,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(require_admin),
):
    """Change a user's enterprise (ADMIN only). Drops existing data source and table permissions to prevent cross-tenant access leakage."""
    user = _get_target_user(user_id, db, admin)
    target_tenant = db.get(Tenant, body.tenant_id)
    if not target_tenant:
        raise HTTPException(status_code=404, detail="Target enterprise not found")

    old_tenant_id = user.tenant_id
    if old_tenant_id != body.tenant_id:
        user.tenant_id = body.tenant_id
        # Revoke existing data source and table permissions as enterprise changed
        db.query(UserTableAccess).filter(UserTableAccess.user_id == user.id).delete(synchronize_session=False)
        db.query(UserDataSourceAccess).filter(UserDataSourceAccess.user_id == user.id).delete(synchronize_session=False)

        audit(
            db,
            tenant_id=body.tenant_id,
            entity_type="users",
            entity_id=user.id,
            action="USER_ENTERPRISE_CHANGED",
            actor=admin.email,
            before={"tenant_id": str(old_tenant_id)},
            after={"tenant_id": str(body.tenant_id)},
            request=request,
        )
        db.commit()
        db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=200)
def disable_user(
    user_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(require_admin),
):
    """Disable (soft-delete) a user."""
    user = _get_target_user(user_id, db, admin)
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot disable your own account")

    user.is_active = False

    audit(
        db,
        tenant_id=user.tenant_id,
        entity_type="users",
        entity_id=user.id,
        action=AuditEvent.USER_DISABLED,
        actor=admin.email,
        before={"email": user.email, "is_active": True},
        after={"is_active": False},
        request=request,
    )

    db.commit()
    return {"status": "disabled"}


@router.get("/{user_id}/sources", response_model=list[UserDataSourceItemOut])
def get_user_sources(
    user_id: uuid.UUID,
    db: Session = Depends(get_session),
    admin: User = Depends(require_admin),
):
    """List all tenant data sources and whether the target user has been granted access."""
    target_user = _get_target_user(user_id, db, admin)

    all_sources = db.scalars(
        select(DataSource).where(DataSource.tenant_id == target_user.tenant_id).order_by(DataSource.name.asc())
    ).all()

    granted_ids = set(
        db.scalars(
            select(UserDataSourceAccess.source_id).where(
                UserDataSourceAccess.tenant_id == target_user.tenant_id,
                UserDataSourceAccess.user_id == user_id
            )
        ).all()
    )

    source_ids = [s.id for s in all_sources]
    total_tables_map: dict[uuid.UUID, int] = {}
    granted_tables_map: dict[uuid.UUID, int] = {}

    if source_ids:
        total_counts = db.execute(
            select(TableMeta.source_id, func.count(TableMeta.id))
            .where(TableMeta.source_id.in_(source_ids))
            .group_by(TableMeta.source_id)
        ).all()
        total_tables_map = {row[0]: row[1] for row in total_counts}

        granted_counts = db.execute(
            select(UserTableAccess.source_id, func.count(UserTableAccess.table_id))
            .where(
                UserTableAccess.tenant_id == target_user.tenant_id,
                UserTableAccess.user_id == user_id,
                UserTableAccess.source_id.in_(source_ids),
            )
            .group_by(UserTableAccess.source_id)
        ).all()
        granted_tables_map = {row[0]: row[1] for row in granted_counts}

    return [
        UserDataSourceItemOut(
            source_id=s.id,
            name=s.name,
            type=s.type,
            database_name=s.database_name,
            is_granted=(s.id in granted_ids or target_user.role == "ADMIN"),
            granted_tables_count=total_tables_map.get(s.id, 0) if target_user.role == "ADMIN" else granted_tables_map.get(s.id, 0),
            total_tables_count=total_tables_map.get(s.id, 0),
        )
        for s in all_sources
    ]


@router.put("/{user_id}/sources", status_code=200)
def update_user_sources(
    user_id: uuid.UUID,
    body: UserDataSourceAccessUpdate,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(require_admin),
):
    """Grant or revoke specific data sources for a user in this tenant."""
    target_user = _get_target_user(user_id, db, admin)

    # Verify all requested source_ids belong to the target user's tenant
    valid_sources = db.scalars(
        select(DataSource.id).where(
            DataSource.tenant_id == target_user.tenant_id,
            DataSource.id.in_(body.source_ids)
        )
    ).all() if body.source_ids else []

    # Transactionally replace grants
    db.execute(
        delete(UserDataSourceAccess).where(
            UserDataSourceAccess.tenant_id == target_user.tenant_id,
            UserDataSourceAccess.user_id == user_id
        )
    )

    for sid in valid_sources:
        db.add(UserDataSourceAccess(
            tenant_id=target_user.tenant_id,
            user_id=user_id,
            source_id=sid,
            granted_by=admin.email,
        ))

    audit(
        db,
        tenant_id=target_user.tenant_id,
        entity_type="user_data_source_access",
        entity_id=user_id,
        action=AuditEvent.USER_ROLE_CHANGED,
        actor=admin.email,
        after={"granted_sources": [str(s) for s in valid_sources]},
        request=request,
    )

    # Clean up table grants for any data sources the user no longer has access to
    if valid_sources:
        db.execute(
            delete(UserTableAccess).where(
                UserTableAccess.tenant_id == target_user.tenant_id,
                UserTableAccess.user_id == user_id,
                UserTableAccess.source_id.not_in(valid_sources)
            )
        )
    else:
        db.execute(
            delete(UserTableAccess).where(
                UserTableAccess.tenant_id == target_user.tenant_id,
                UserTableAccess.user_id == user_id,
            )
        )

    db.commit()
    return {"status": "updated", "granted_count": len(valid_sources)}


@router.get("/{user_id}/sources/{source_id}/tables", response_model=list[UserTableAccessItemOut])
def get_user_source_tables(
    user_id: uuid.UUID,
    source_id: uuid.UUID,
    db: Session = Depends(get_session),
    admin: User = Depends(require_admin),
):
    """List all discovered tables for a data source and whether the target user has table-level access."""
    target_user = _get_target_user(user_id, db, admin)

    source = db.scalar(
        select(DataSource).where(DataSource.id == source_id, DataSource.tenant_id == target_user.tenant_id)
    )
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")

    tables = db.scalars(
        select(TableMeta).where(TableMeta.source_id == source_id).order_by(TableMeta.schema_name.asc(), TableMeta.table_name.asc())
    ).all()

    granted_table_ids = set(
        db.scalars(
            select(UserTableAccess.table_id).where(
                UserTableAccess.tenant_id == target_user.tenant_id,
                UserTableAccess.user_id == user_id,
                UserTableAccess.source_id == source_id,
            )
        ).all()
    )

    return [
        UserTableAccessItemOut(
            table_id=t.id,
            schema_name=t.schema_name,
            table_name=t.table_name,
            business_name=t.business_name,
            description=t.description,
            row_count=t.row_count,
            is_granted=(t.id in granted_table_ids or target_user.role == "ADMIN")
        )
        for t in tables
    ]


@router.put("/{user_id}/sources/{source_id}/tables", status_code=200)
def update_user_source_tables(
    user_id: uuid.UUID,
    source_id: uuid.UUID,
    body: UserTableAccessUpdate,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(require_admin),
):
    """Configure table-level permissions for a user within a data source."""
    target_user = _get_target_user(user_id, db, admin)

    source = db.scalar(
        select(DataSource).where(DataSource.id == source_id, DataSource.tenant_id == target_user.tenant_id)
    )
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")

    # Verify all requested table_ids belong to this source
    valid_tables = db.scalars(
        select(TableMeta.id).where(
            TableMeta.source_id == source_id,
            TableMeta.id.in_(body.table_ids)
        )
    ).all() if body.table_ids else []

    # Transactionally replace table grants for this source
    db.execute(
        delete(UserTableAccess).where(
            UserTableAccess.tenant_id == target_user.tenant_id,
            UserTableAccess.user_id == user_id,
            UserTableAccess.source_id == source_id,
        )
    )

    for tid in valid_tables:
        db.add(UserTableAccess(
            tenant_id=target_user.tenant_id,
            user_id=user_id,
            source_id=source_id,
            table_id=tid,
            granted_by=admin.email,
        ))

    # Auto-synchronize parent data source access:
    # If table grants are assigned, ensure the user has access to the parent data source
    if valid_tables:
        existing_parent = db.scalar(
            select(UserDataSourceAccess).where(
                UserDataSourceAccess.tenant_id == target_user.tenant_id,
                UserDataSourceAccess.user_id == user_id,
                UserDataSourceAccess.source_id == source_id,
            )
        )
        if not existing_parent:
            db.add(UserDataSourceAccess(
                tenant_id=target_user.tenant_id,
                user_id=user_id,
                source_id=source_id,
                granted_by=admin.email,
            ))

    audit(
        db,
        tenant_id=target_user.tenant_id,
        entity_type="user_table_access",
        entity_id=user_id,
        action=AuditEvent.USER_ROLE_CHANGED,
        actor=admin.email,
        after={"source_id": str(source_id), "granted_tables": [str(t) for t in valid_tables]},
        request=request,
    )

    db.commit()
    return {"status": "updated", "granted_tables_count": len(valid_tables)}


@router.post("/{user_id}/reset-password", status_code=200)
def reset_user_password(
    user_id: uuid.UUID,
    body: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(require_admin),
):
    """Admin resets a user's password securely."""
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")

    target_user = _get_target_user(user_id, db, admin)

    target_user.password_hash = get_password_hash(body.new_password)
    audit(
        db,
        tenant_id=target_user.tenant_id,
        entity_type="users",
        entity_id=target_user.id,
        action=AuditEvent.USER_ROLE_CHANGED,
        actor=admin.email,
        after={"action": "password_reset"},
        request=request,
    )
    db.commit()
    return {"status": "password_reset_success"}


@router.put("/{user_id}/status", status_code=200)
def update_user_status(
    user_id: uuid.UUID,
    body: UserStatusUpdate,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(require_admin),
):
    """Admin activates or deactivates a user."""
    target_user = _get_target_user(user_id, db, admin)
    if target_user.id == admin.id and not body.is_active:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    target_user.is_active = body.is_active
    audit(
        db,
        tenant_id=target_user.tenant_id,
        entity_type="users",
        entity_id=target_user.id,
        action=AuditEvent.USER_ROLE_CHANGED,
        actor=admin.email,
        after={"is_active": body.is_active},
        request=request,
    )
    db.commit()
    return {"status": "status_updated", "is_active": target_user.is_active}

