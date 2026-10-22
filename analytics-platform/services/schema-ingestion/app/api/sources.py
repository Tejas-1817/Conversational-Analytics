import shutil
import uuid
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, File, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.api.deps import Permission, require_admin, require_permission, verify_tenant_owns, verify_user_has_source_access
from app.audit import AuditEvent, audit
from app.config import get_settings
from app.connectors.factory import build_engine, test_connection, verify_read_only
from app.db import get_session
from app.ingestion.excel_ingestor import preview_excel_sheets
from app.models import DataSource, User
from app.schemas import (
    DataSourceCreate,
    DataSourceEnterpriseUpdate,
    DataSourceOut,
    ExcelPreviewResponse,
    ExcelSourceCreate,
    SourceUserAccessItemOut,
    SourceUserAccessUpdate,
)
from app.security.crypto import encrypt_secret

log = structlog.get_logger()
router = APIRouter(prefix="/sources", tags=["sources"])


@router.post("", response_model=DataSourceOut, status_code=201)
def create_source(
    payload: DataSourceCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> DataSource:

    # dedicated_tenant_id = uuid.uuid4()

    target_tenant_id = (
        payload.tenant_id if (payload.tenant_id and current_user.role == "ADMIN") 
        else current_user.tenant_id
    )
    source = DataSource(
        tenant_id=target_tenant_id,
        name=payload.name,
    type=payload.type,
    host=payload.host,
    port=payload.port,
    database_name=payload.database_name,
    username=payload.username,
    credentials_encrypted=encrypt_secret(
        payload.password.get_secret_value()
    ),
    ssl_mode=payload.ssl_mode,
    options=payload.options.model_dump(),
    created_by=current_user.email,
    updated_by=current_user.email,
)
    session.add(source)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409, 
            detail=f"A data source named '{payload.name}' already exists in your workspace."
        )

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

    # Trigger automated 5-stage schema extraction workflow immediately
    from app.models import IngestionJob
    from app.ingestion.pipeline import run_pipeline
    job = IngestionJob(source_id=source.id, stage="Connection Validation", status="running")
    session.add(job)
    session.commit()

    background_tasks.add_task(run_pipeline, str(job.id), str(source.id))

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


@router.post("/excel/preview", response_model=ExcelPreviewResponse)
async def preview_excel_source(
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
) -> ExcelPreviewResponse:
    """Accepts an uploaded .xlsx file and returns sheet previews without materializing to SQLite."""
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Only Excel (.xlsx) files are supported."
        )

    settings = get_settings()
    max_bytes = settings.excel_max_upload_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum allowed size of {settings.excel_max_upload_mb}MB."
        )

    temp_id = str(uuid.uuid4())
    temp_dir = Path(settings.excel_upload_dir) / str(current_user.tenant_id) / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"{temp_id}.xlsx"
    temp_path.write_bytes(content)

    try:
        preview_data = preview_excel_sheets(temp_path)
    except Exception as exc:
        log.error("excel_preview_failed", error=str(exc))
        raise HTTPException(status_code=400, detail=f"Failed to parse Excel workbook: {exc}") from exc

    return ExcelPreviewResponse(
        temp_file_id=temp_id,
        filename=file.filename,
        sheets=preview_data.get("sheets", [])
    )


@router.post("/excel", response_model=DataSourceOut, status_code=201)
def create_excel_source(
    payload: ExcelSourceCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> DataSource:
    """Creates a new Excel-backed DataSource with confirmed sheet overrides and enqueues ingestion."""
    settings = get_settings()
    temp_path = Path(settings.excel_upload_dir) / str(current_user.tenant_id) / "temp" / f"{payload.temp_file_id}.xlsx"
    if not temp_path.exists():
        raise HTTPException(
            status_code=400,
            detail="Uploaded file session expired or not found. Please upload the file again."
        )

    source_id = uuid.uuid4()
    final_dir = Path(settings.excel_upload_dir) / str(current_user.tenant_id) / str(source_id)
    final_dir.mkdir(parents=True, exist_ok=True)
    final_upload_path = (final_dir / "original.xlsx").resolve().as_posix()
    
    shutil.copy2(str(temp_path), final_upload_path)

    options = dict(payload.options)
    # Serialize sheet overrides
    options["sheet_overrides"] = {k: v.model_dump() for k, v in payload.sheet_overrides.items()}

    source = DataSource(
        id=source_id,
        tenant_id=current_user.tenant_id,
        name=payload.name,
        type="excel",
        original_upload_path=final_upload_path,
        options=options,
        created_by=current_user.email,
        updated_by=current_user.email,
    )
    session.add(source)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"A data source named '{payload.name}' already exists in your workspace."
        )

    from app.models import IngestionJob
    from app.ingestion.pipeline import run_pipeline
    job = IngestionJob(source_id=source.id, stage="Excel Materialization", status="running")
    session.add(job)
    session.commit()

    background_tasks.add_task(run_pipeline, str(job.id), str(source.id))

    audit(
        session,
        tenant_id=current_user.tenant_id,
        entity_type="data_sources",
        entity_id=source.id,
        action=AuditEvent.SOURCE_REGISTERED,
        actor=current_user.email,
        after={"name": source.name, "type": source.type, "original_upload_path": source.original_upload_path},
        request=request,
    )

    session.commit()
    log.info("excel_source_registered", source=payload.name, source_id=str(source.id))
    return source


@router.get("", response_model=list[DataSourceOut])
def list_sources(
    tenant_id: uuid.UUID | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission(Permission.VIEW_SOURCES)),
) -> list[DataSource]:
    query = session.query(DataSource)
    if current_user.role == "ADMIN":
        if tenant_id is not None:
            query = query.filter(DataSource.tenant_id == tenant_id)
    else:
        query = query.filter(DataSource.tenant_id == current_user.tenant_id)
        from app.models import UserDataSourceAccess
        allowed_ids = (
            session.query(UserDataSourceAccess.source_id)
            .filter(
                UserDataSourceAccess.tenant_id == current_user.tenant_id,
                UserDataSourceAccess.user_id == current_user.id,
            )
            .subquery()
        )
        query = query.filter(DataSource.id.in_(allowed_ids))
    return query.order_by(DataSource.created_at.desc()).all()


@router.patch("/{source_id}/enterprise", response_model=DataSourceOut)
def update_source_enterprise(
    source_id: uuid.UUID,
    body: DataSourceEnterpriseUpdate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> DataSource:
    """Reassign a data source to an enterprise (ADMIN only). Purges user grants to avoid cross-tenant leaks."""
    source = session.get(DataSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    from app.models import Tenant, UserDataSourceAccess, UserTableAccess
    target_tenant = session.get(Tenant, body.tenant_id)
    if not target_tenant:
        raise HTTPException(status_code=404, detail="Target enterprise not found")

    old_tenant_id = source.tenant_id
    if old_tenant_id != body.tenant_id:
        source.tenant_id = body.tenant_id
        # Purge existing user grants to avoid cross-tenant access leaks
        session.query(UserTableAccess).filter(UserTableAccess.source_id == source.id).delete(synchronize_session=False)
        session.query(UserDataSourceAccess).filter(UserDataSourceAccess.source_id == source.id).delete(synchronize_session=False)

        audit(
            session,
            tenant_id=body.tenant_id,
            entity_type="data_sources",
            entity_id=source.id,
            action="DATA_SOURCE_ENTERPRISE_CHANGED",
            actor=current_user.email,
            before={"tenant_id": str(old_tenant_id)},
            after={"tenant_id": str(body.tenant_id)},
            request=request,
        )
        session.commit()
        session.refresh(source)
    return source

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
        credentials_encrypted=encrypt_secret(
        payload.password.get_secret_value()
    ),
    ssl_mode=payload.ssl_mode,
    options=payload.options.model_dump(),
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

    # Clean up related entities
    from app.models import (
        IngestionJob, SemanticModel, MetadataVersion,
        SemanticDimension, SemanticMetric, SemanticKPI,
        BusinessGlossary, SemanticJoin
    )

    # Delete ingestion jobs and metadata versions
    session.query(IngestionJob).filter(IngestionJob.source_id == source.id).delete(synchronize_session=False)
    session.query(MetadataVersion).filter(MetadataVersion.source_id == source.id).delete(synchronize_session=False)

    # Get semantic model IDs for this source
    semantic_model_ids = [
        sm.id for sm in session.query(SemanticModel).filter(SemanticModel.source_id == source.id).all()
    ]

    # Clean up all child entities of those semantic models
    if semantic_model_ids:
        session.query(SemanticDimension).filter(SemanticDimension.semantic_model_id.in_(semantic_model_ids)).delete(synchronize_session=False)
        session.query(SemanticMetric).filter(SemanticMetric.semantic_model_id.in_(semantic_model_ids)).delete(synchronize_session=False)
        session.query(SemanticKPI).filter(SemanticKPI.semantic_model_id.in_(semantic_model_ids)).delete(synchronize_session=False)
        session.query(BusinessGlossary).filter(BusinessGlossary.semantic_model_id.in_(semantic_model_ids)).delete(synchronize_session=False)
        session.query(SemanticJoin).filter(SemanticJoin.semantic_model_id.in_(semantic_model_ids)).delete(synchronize_session=False)
        
        # Finally delete the semantic models
        session.query(SemanticModel).filter(SemanticModel.source_id == source.id).delete(synchronize_session=False)

    session.delete(source)
    session.commit()
    log.info("source_deleted", source_id=str(source_id), actor=current_user.email)


from pathlib import Path
from fastapi.responses import FileResponse, PlainTextResponse

@router.get("/{source_id}/schemas/active")
def get_active_schema_file(
    source_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission(Permission.VIEW_SOURCES)),
):
    source = session.get(DataSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    verify_tenant_owns(source.tenant_id, current_user)
    verify_user_has_source_access(session, current_user, source.id)
    
    from app.models import SchemaRegistry
    registry = session.query(SchemaRegistry).filter_by(source_id=source.id, is_active=True).first()
    if not registry or not Path(registry.file_path).exists():
        from app.chat_sql.schema_provider import SchemaProvider
        _, schema_text = SchemaProvider().get_connected_schema(db_session=session, user=current_user, source=source)
        return PlainTextResponse(
            content=schema_text,
            headers={"Content-Disposition": f'attachment; filename="schema_{source_id}.txt"'}
        )
    
    return FileResponse(
        path=registry.file_path,
        filename=Path(registry.file_path).name,
        media_type="text/plain",
        content_disposition_type="attachment"
    )


@router.get("/schemas/{schema_id}/download")
def download_schema_registry_file(
    schema_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_permission(Permission.VIEW_SOURCES)),
):
    from app.models import SchemaRegistry
    registry = session.get(SchemaRegistry, schema_id)
    if not registry:
        raise HTTPException(status_code=404, detail="Schema file not found")
    verify_tenant_owns(registry.tenant_id, current_user)
    verify_user_has_source_access(session, current_user, registry.source_id)
    
    if not Path(registry.file_path).exists():
        raise HTTPException(status_code=404, detail="Physical schema file missing on disk")
        
    return FileResponse(
        path=registry.file_path,
        filename=Path(registry.file_path).name,
        media_type="text/plain",
        content_disposition_type="attachment"
    )


@router.get("/{source_id}/users", response_model=list[SourceUserAccessItemOut])
def get_source_users(
    source_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> list[SourceUserAccessItemOut]:
    source = session.get(DataSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    verify_tenant_owns(source.tenant_id, current_user)

    from app.models import UserDataSourceAccess
    users = (
        session.query(User)
        .filter(User.tenant_id == current_user.tenant_id)
        .order_by(User.email.asc())
        .all()
    )

    granted_user_ids = set(
        session.scalars(
            select(UserDataSourceAccess.user_id).where(
                UserDataSourceAccess.tenant_id == current_user.tenant_id,
                UserDataSourceAccess.source_id == source_id,
            )
        ).all()
    )

    return [
        SourceUserAccessItemOut(
            user_id=u.id,
            email=u.email,
            role=u.role,
            is_granted=(u.id in granted_user_ids or u.role == "ADMIN"),
        )
        for u in users
    ]


@router.put("/{source_id}/users", status_code=200)
def update_source_users(
    source_id: uuid.UUID,
    body: SourceUserAccessUpdate,
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> dict:
    source = session.get(DataSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    verify_tenant_owns(source.tenant_id, current_user)

    from app.models import UserDataSourceAccess
    valid_users = (
        session.scalars(
            select(User.id).where(
                User.tenant_id == current_user.tenant_id,
                User.id.in_(body.user_ids),
                User.role != "ADMIN",
            )
        ).all()
        if body.user_ids
        else []
    )

    session.execute(
        delete(UserDataSourceAccess).where(
            UserDataSourceAccess.tenant_id == current_user.tenant_id,
            UserDataSourceAccess.source_id == source_id,
        )
    )

    for uid in valid_users:
        session.add(
            UserDataSourceAccess(
                tenant_id=current_user.tenant_id,
                user_id=uid,
                source_id=source_id,
                granted_by=current_user.email,
            )
        )

    audit(
        session,
        tenant_id=current_user.tenant_id,
        entity_type="user_data_source_access",
        entity_id=source_id,
        action=AuditEvent.USER_ROLE_CHANGED,
        actor=current_user.email,
        after={"granted_users": [str(u) for u in valid_users]},
        request=request,
    )

    session.commit()
    return {"status": "updated", "granted_count": len(valid_users)}


