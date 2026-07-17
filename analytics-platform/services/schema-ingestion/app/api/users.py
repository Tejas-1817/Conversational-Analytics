"""User management — fully tenant-scoped with audit logging."""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Permission, require_admin, require_permission
from app.audit import AuditEvent, audit
from app.db import get_session
from app.models import User
from app.security.auth import get_password_hash

router = APIRouter(prefix="/users", tags=["users"])


# --- Schemas ---

class UserCreate(BaseModel):
    email: str
    password: str
    role: str = "VIEWER"


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserRoleUpdate(BaseModel):
    role: str


# --- Endpoints ---

@router.get("", response_model=list[UserOut])
def get_users(
    db: Session = Depends(get_session),
    admin: User = Depends(require_permission(Permission.VIEW_USERS)),
):
    """List users scoped strictly to the calling user's tenant."""
    return db.scalars(
        select(User).where(User.tenant_id == admin.tenant_id).order_by(User.created_at.desc())
    ).all()


@router.post("", response_model=UserOut, status_code=201)
def invite_user(
    user_in: UserCreate,
    request: Request,
    db: Session = Depends(get_session),
    admin: User = Depends(require_admin),
):
    """Invite a new user to the calling admin's tenant."""
    if user_in.role not in ("ADMIN", "ANALYST", "VIEWER"):
        raise HTTPException(status_code=400, detail=f"Invalid role: {user_in.role}")

    existing = db.scalar(
        select(User).where(User.tenant_id == admin.tenant_id, User.email == user_in.email)
    )
    if existing:
        raise HTTPException(status_code=400, detail="User already exists in this tenant")

    db_obj = User(
        tenant_id=admin.tenant_id,
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        role=user_in.role,
    )
    db.add(db_obj)
    db.flush()

    audit(
        db,
        tenant_id=admin.tenant_id,
        entity_type="users",
        entity_id=db_obj.id,
        action=AuditEvent.USER_CREATED,
        actor=admin.email,
        after={"email": user_in.email, "role": user_in.role},
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
    """Change a user's role. Only allowed within the same tenant."""
    if body.role not in ("ADMIN", "ANALYST", "VIEWER"):
        raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")

    user = db.scalar(
        select(User).where(User.id == user_id, User.tenant_id == admin.tenant_id)
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old_role = user.role
    user.role = body.role

    audit(
        db,
        tenant_id=admin.tenant_id,
        entity_type="users",
        entity_id=user.id,
        action=AuditEvent.USER_ROLE_CHANGED,
        actor=admin.email,
        before={"role": old_role},
        after={"role": body.role},
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
    """Disable (soft-delete) a user. Only allowed within the same tenant."""
    user = db.scalar(
        select(User).where(User.id == user_id, User.tenant_id == admin.tenant_id)
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot disable your own account")

    user.is_active = False

    audit(
        db,
        tenant_id=admin.tenant_id,
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
