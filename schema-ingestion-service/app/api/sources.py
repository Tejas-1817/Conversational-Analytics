"""Data source registration and connection testing."""
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_api_key
from app.config import get_settings
from app.connectors.factory import build_engine, test_connection, verify_read_only
from app.db import get_session
from app.models import DataSource
from app.schemas import DataSourceCreate, DataSourceOut
from app.security.crypto import encrypt_secret

log = structlog.get_logger()
router = APIRouter(prefix="/sources", tags=["sources"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=DataSourceOut, status_code=201)
def create_source(payload: DataSourceCreate, session: Session = Depends(get_session)) -> DataSource:
    source = DataSource(
        tenant_id=uuid.UUID(get_settings().default_tenant_id),
        name=payload.name, type=payload.type, host=payload.host, port=payload.port,
        database_name=payload.database_name, username=payload.username,
        credentials_encrypted=encrypt_secret(payload.password),
        options=payload.options, created_by="api", updated_by="api",
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
    log.info("source_registered", source=payload.name, type=payload.type)
    return source


@router.get("", response_model=list[DataSourceOut])
def list_sources(session: Session = Depends(get_session)) -> list[DataSource]:
    return session.query(DataSource).order_by(DataSource.created_at.desc()).all()


@router.post("/{source_id}/test", response_model=dict)
def test_source(source_id: uuid.UUID, session: Session = Depends(get_session)) -> dict:
    source = session.get(DataSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    engine = build_engine(source)
    try:
        test_connection(engine)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Connection failed: {exc}") from exc
    finally:
        engine.dispose()
    return {"ok": True}
