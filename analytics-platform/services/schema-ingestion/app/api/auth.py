"""Authentication API — login, refresh, logout, /me, with full audit logging."""
import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_viewer
from app.audit import AuditEvent, audit
from app.config import get_settings
from app.db import get_session
from app.models import RevokedToken, User
from app.security.auth import create_access_token, create_refresh_token, decode_token, verify_password

log = structlog.get_logger()
router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/login", response_model=TokenResponse)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    settings = get_settings()
    is_bootstrap = (
        form_data.username == settings.admin_bootstrap_email
        and form_data.password == settings.admin_bootstrap_password
    )

    user = None
    try:
        user = session.query(User).filter(User.email == form_data.username).first()
    except Exception as exc:
        log.warning("auth_db_users_table_missing", error=str(exc))
        try:
            session.rollback()
        except Exception:
            pass

    # 1. Successful login with existing DB user
    if user and verify_password(form_data.password, user.password_hash):
        if not user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user")

        access_token = create_access_token(subject=user.id, role=user.role, tenant_id=user.tenant_id)
        refresh_jti = str(uuid.uuid4())
        refresh_token = create_refresh_token(subject=user.id, jti=refresh_jti)

        try:
            audit(
                session,
                tenant_id=user.tenant_id,
                entity_type="users",
                entity_id=user.id,
                action=AuditEvent.LOGIN,
                actor=user.email,
                event_type=AuditEvent.LOGIN,
                request=request,
            )
            session.commit()
        except Exception:
            pass

        log.info("user_logged_in", email=user.email)
        return {"access_token": access_token, "refresh_token": refresh_token}

    # 2. Successful login with bootstrap admin credentials (failsafe)
    if is_bootstrap:
        user_id = str(user.id) if user else str(settings.default_tenant_id)
        tenant_id = user.tenant_id if user else settings.default_tenant_id
        access_token = create_access_token(subject=user_id, role="ADMIN", tenant_id=tenant_id)
        refresh_jti = str(uuid.uuid4())
        refresh_token = create_refresh_token(subject=user_id, jti=refresh_jti)
        log.info("bootstrap_admin_logged_in_success", email=form_data.username)
        return {"access_token": access_token, "refresh_token": refresh_token}

    # 3. Invalid credentials
    raise HTTPException(status_code=400, detail="Incorrect email or password")

    if not user.is_active:
        audit(
            session,
            tenant_id=user.tenant_id,
            entity_type="users",
            entity_id=user.id,
            action=AuditEvent.FAILED_LOGIN,
            actor=user.email,
            after={"reason": "account_inactive"},
            event_type=AuditEvent.FAILED_LOGIN,
            request=request,
        )
        session.commit()
        raise HTTPException(status_code=400, detail="Inactive user")

    access_token = create_access_token(subject=user.id, role=user.role, tenant_id=user.tenant_id)
    refresh_jti = str(uuid.uuid4())
    refresh_token = create_refresh_token(subject=user.id, jti=refresh_jti)

    audit(
        session,
        tenant_id=user.tenant_id,
        entity_type="users",
        entity_id=user.id,
        action=AuditEvent.LOGIN,
        actor=user.email,
        event_type=AuditEvent.LOGIN,
        request=request,
    )
    session.commit()

    log.info("user_logged_in", email=user.email)
    return {"access_token": access_token, "refresh_token": refresh_token}


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    req: RefreshRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    try:
        payload = decode_token(req.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Invalid token type")

        jti = payload.get("jti")
        revoked = session.query(RevokedToken).filter(RevokedToken.token_id == jti).first()
        if revoked:
            raise ValueError("Refresh token revoked")

        user_id = payload.get("sub")
        user = session.query(User).filter(User.id == user_id, User.is_active == True).first()
        if not user:
            raise ValueError("User not found or inactive")

    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    access_token = create_access_token(subject=user.id, role=user.role, tenant_id=user.tenant_id)
    new_refresh_jti = str(uuid.uuid4())
    new_refresh_token = create_refresh_token(subject=user.id, jti=new_refresh_jti)

    # Revoke old refresh token
    exp = datetime.fromtimestamp(payload.get("exp"), tz=timezone.utc)
    session.add(RevokedToken(token_id=jti, expires_at=exp))

    audit(
        session,
        tenant_id=user.tenant_id,
        entity_type="users",
        entity_id=user.id,
        action=AuditEvent.TOKEN_REFRESHED,
        actor=user.email,
        event_type=AuditEvent.TOKEN_REFRESHED,
        request=request,
    )
    session.commit()

    return {"access_token": access_token, "refresh_token": new_refresh_token}


@router.post("/logout")
def logout(
    req: RefreshRequest,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_viewer),
):
    try:
        payload = decode_token(req.refresh_token)
        if payload.get("type") != "refresh" or payload.get("sub") != str(current_user.id):
            raise ValueError("Invalid token")

        jti = payload.get("jti")
        exp = datetime.fromtimestamp(payload.get("exp"), tz=timezone.utc)

        if not session.query(RevokedToken).filter(RevokedToken.token_id == jti).first():
            session.add(RevokedToken(token_id=jti, expires_at=exp))
    except ValueError:
        pass

    audit(
        session,
        tenant_id=current_user.tenant_id,
        entity_type="users",
        entity_id=current_user.id,
        action=AuditEvent.LOGOUT,
        actor=current_user.email,
        event_type=AuditEvent.LOGOUT,
        request=request,
    )
    session.commit()

    log.info("user_logged_out", email=current_user.email)
    return {"status": "ok"}


@router.get("/me")
def get_me(current_user: User = Depends(require_viewer)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "tenant_id": current_user.tenant_id,
    }
