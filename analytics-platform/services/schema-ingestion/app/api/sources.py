"""Data source registration and connection testing."""
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import Permission, require_admin, require_permission, verify_tenant_owns
from app.audit import AuditEvent, audit
from app.connectors.factory import build_engine, test_connection, verify_read_only
from app.db import get_session
from app.models import DataSource, User
from app.schemas import DataSourceCreate, DataSourceOut
from app.security.crypto import encrypt_secret

log = structlog.get_logger()
router = APIRouter(prefix="/sources", tags=["sources"])


@router.post("", response_model=DataSourceOut, status_code=201)
def create_source(
    payload: DataSourceCreate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> DataSource:
    source = DataSource(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        type=payload.type,
        host=payload.host,
        port=payload.port,
        database_name=payload.database_name,
        username=payload.username,
        credentials_encrypted=encrypt_secret(payload.password),
        options=payload.options,
        created_by=current_user.email,
        updated_by=current_user.email,
    )
    session.add(source)
    session.flush()

    # Fail registration early if unreachable or writable
    try:
        engine = build_engine(source)
        try:
            test_connection(engine)
            verify_read_only(engine, source.type)
        finally:
            engine.dispose()
    except NotImplementedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        log.warning("connection_test_failed", source=payload.name, error=str(exc))
        raise HTTPException(status_code=400, detail=f"Connection test failed: {exc}") from exc

    source.status = "connected"

    audit(
        session,
        tenant_id=current_user.tenant_id,
        entity_type="data_sources",
        entity_id=source.id,
        action=AuditEvent.SOURCE_REGISTERED,
        actor=current_user.email,
        after={"name": source.name, "type": source.type, "host": source.host},
        request=request,
    )

    session.commit()
    log.info("source_registered", source=payload.name, type=payload.type)
    return source


@router.get("", response_model=list[DataSourceOut])
def list_sources(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission(Permission.VIEW_SOURCES)),
) -> list[DataSource]:
    # SECURITY FIX: filter by tenant_id — previously returned ALL sources cross-tenant
    return (
        session.query(DataSource)
        .filter(DataSource.tenant_id == current_user.tenant_id)
        .order_by(DataSource.created_at.desc())
        .all()
    )

@router.post("/test", response_model=dict)
def test_new_source(
    payload: DataSourceCreate,
    current_user: User = Depends(require_admin),
) -> dict:
    source = DataSource(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        type=payload.type,
        host=payload.host,
        port=payload.port,
        database_name=payload.database_name,
        username=payload.username,
        credentials_encrypted=encrypt_secret(payload.password),
        options=payload.options,
    )

    try:
        engine = build_engine(source)
        try:
            test_connection(engine)
            verify_read_only(engine, source.type)
        finally:
            engine.dispose()
    except NotImplementedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        log.warning("connection_test_failed_preview", source=payload.name, error=str(exc))
        raise HTTPException(status_code=400, detail=f"Connection test failed: {exc}") from exc

    return {"ok": True}


@router.post("/{source_id}/test", response_model=dict)
def test_source(
    source_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> dict:
    source = session.get(DataSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    # Tenant ownership check
    verify_tenant_owns(source.tenant_id, current_user)

    engine = build_engine(source)
    try:
        test_connection(engine)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Connection failed: {exc}") from exc
    finally:
        engine.dispose()
    return {"ok": True}


@router.delete("/{source_id}", status_code=204)
def delete_source(
    source_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> None:
    source = session.get(DataSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    verify_tenant_owns(source.tenant_id, current_user)

    audit(
        session,
        tenant_id=current_user.tenant_id,
        entity_type="data_sources",
        entity_id=source.id,
        action=AuditEvent.SOURCE_DELETED,
        actor=current_user.email,
        before={"name": source.name, "type": source.type},
        request=request,
    )

    session.delete(source)
    session.commit()
    log.info("source_deleted", source_id=str(source_id), actor=current_user.email)
