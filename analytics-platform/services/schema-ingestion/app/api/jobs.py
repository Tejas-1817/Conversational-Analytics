"""Trigger and monitor ingestion jobs (async via RQ)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from redis import Redis
from rq import Queue
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_viewer, verify_tenant_owns
from app.config import get_settings
from app.db import get_session
from app.ingestion.pipeline import run_pipeline
from app.models import DataSource, IngestionJob, User
from app.schemas import JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _queue() -> Queue:
    settings = get_settings()
    return Queue("ingestion", connection=Redis.from_url(settings.redis_url),
                 default_timeout=settings.job_timeout_seconds)


@router.post("/ingest/{source_id}", response_model=JobOut, status_code=202)
def trigger_ingestion(
    source_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
) -> IngestionJob:
    from datetime import datetime, timezone, timedelta
    source = session.get(DataSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    # Tenant isolation — admin can only trigger jobs for their own tenant's sources
    verify_tenant_owns(source.tenant_id, current_user)

    stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=2)
    running_jobs = (
        session.query(IngestionJob)
        .filter(IngestionJob.source_id == source_id, IngestionJob.status.in_(["queued", "running"]))
        .all()
    )

    for r_job in running_jobs:
        # If job created over 2 minutes ago and still running, mark as timed out so user can re-run
        job_created = r_job.created_at
        if job_created and job_created.tzinfo is None:
            job_created = job_created.replace(tzinfo=timezone.utc)
        if job_created and job_created < stale_cutoff:
            r_job.status = "failed"
            r_job.error = "Job timed out or worker was restarted"
            session.commit()
        else:
            raise HTTPException(status_code=409, detail=f"Job {r_job.id} is already {r_job.status}")

    init_stage = "Excel Materialization" if source.type == "excel" else "Connection Validation"
    job = IngestionJob(source_id=source_id, stage=init_stage, status="running")
    session.add(job)
    session.commit()

    # Enqueue in Redis Queue; if queue is offline or no worker, run via FastAPI background tasks
    enqueued = False
    try:
        q = _queue()
        # Verify redis is alive and has workers
        q.enqueue(run_pipeline, str(job.id), str(source_id), job_id=str(job.id))
        enqueued = True
    except Exception:
        enqueued = False

    if not enqueued:
        background_tasks.add_task(run_pipeline, str(job.id), str(source_id))

    return job


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: uuid.UUID, session: Session = Depends(get_session), current_user: User = Depends(require_viewer)) -> IngestionJob:
    """Return a job only if it belongs to the calling user's tenant (via source FK)."""
    job = session.scalar(
        select(IngestionJob)
        .join(DataSource, IngestionJob.source_id == DataSource.id)
        .where(
            IngestionJob.id == job_id,
            DataSource.tenant_id == current_user.tenant_id,
        )
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("", response_model=list[JobOut])
def list_jobs(session: Session = Depends(get_session), current_user: User = Depends(require_viewer)) -> list[IngestionJob]:
    """List jobs scoped to the calling user's tenant via source FK."""
    return session.scalars(
        select(IngestionJob)
        .join(DataSource, IngestionJob.source_id == DataSource.id)
        .where(DataSource.tenant_id == current_user.tenant_id)
        .order_by(IngestionJob.created_at.desc())
        .limit(50)
    ).all()
