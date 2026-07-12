"""Trigger and monitor ingestion jobs (async via RQ)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from redis import Redis
from rq import Queue
from sqlalchemy.orm import Session

from app.api.deps import require_api_key
from app.config import get_settings
from app.db import get_session
from app.ingestion.pipeline import run_pipeline
from app.models import DataSource, IngestionJob
from app.schemas import JobOut

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(require_api_key)])


def _queue() -> Queue:
    settings = get_settings()
    return Queue("ingestion", connection=Redis.from_url(settings.redis_url),
                 default_timeout=settings.job_timeout_seconds)


@router.post("/ingest/{source_id}", response_model=JobOut, status_code=202)
def trigger_ingestion(source_id: uuid.UUID, session: Session = Depends(get_session)) -> IngestionJob:
    source = session.get(DataSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    running = (session.query(IngestionJob)
               .filter(IngestionJob.source_id == source_id, IngestionJob.status.in_(["queued", "running"]))
               .first())
    if running is not None:
        raise HTTPException(status_code=409, detail=f"Job {running.id} is already {running.status}")

    job = IngestionJob(source_id=source_id)
    session.add(job)
    session.flush()
    _queue().enqueue(run_pipeline, str(job.id), str(source_id), job_id=str(job.id))
    return job


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: uuid.UUID, session: Session = Depends(get_session)) -> IngestionJob:
    job = session.get(IngestionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("", response_model=list[JobOut])
def list_jobs(session: Session = Depends(get_session)) -> list[IngestionJob]:
    return session.query(IngestionJob).order_by(IngestionJob.created_at.desc()).limit(50).all()
