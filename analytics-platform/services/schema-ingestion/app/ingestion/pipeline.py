"""Ingestion pipeline — orchestrates all stages for one data source.

Runs as an RQ job. Stage order: introspect -> profile -> relationships -> classify.
Each stage's stats and any failure are recorded on the ingestion_jobs row.
"""
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import func

from app.connectors.factory import build_engine
from app.db import session_scope
from app.ingestion.classifier import run_classification
from app.ingestion.introspector import run_introspection
from app.ingestion.profiler import run_profiling
from app.ingestion.relationships import run_relationship_detection
from app.ingestion.semantic_generator import run_semantic_generation
from app.models import DataSource, IngestionJob, MetadataVersion

log = structlog.get_logger()


def run_pipeline(job_id: str, source_id: str) -> None:
    """RQ entry point. Signature must stay picklable (str UUIDs)."""
    with session_scope() as session:
        job = session.get(IngestionJob, uuid.UUID(job_id))
        source = session.get(DataSource, uuid.UUID(source_id))
        if job is None or source is None:
            log.error("job_or_source_missing", job_id=job_id, source_id=source_id)
            return

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)

        # Create MetadataVersion
        max_version = session.query(func.max(MetadataVersion.version_number)).filter_by(source_id=source.id).scalar() or 0
        version = MetadataVersion(
            source_id=source.id,
            version_number=max_version + 1,
            sync_status="running"
        )
        session.add(version)
        session.commit()

        engine = None
        try:
            engine = build_engine(source)
            stats: dict = {}

            for stage_name, runner in (
                ("introspect", lambda: run_introspection(session, source, engine)),
                ("profile", lambda: run_profiling(session, source, engine)),
                ("relationships", lambda: run_relationship_detection(session, source, engine)),
                ("classify", lambda: run_classification(session, source)),
                ("semantic_generation", lambda: run_semantic_generation(session, source, version.id)),
            ):
                job.stage = stage_name
                session.commit()
                log.info("stage_started", stage=stage_name, source=source.name)
                stats[stage_name] = runner()
                job.stats = dict(stats)
                session.commit()
                log.info("stage_finished", stage=stage_name, **stats[stage_name])

            source.last_ingested_at = datetime.now(timezone.utc)
            job.status = "succeeded"
            version.sync_status = "succeeded"
        except Exception as exc:
            log.exception("pipeline_failed", source=source.name)
            job.status = "failed"
            job.error = f"{type(exc).__name__}: {exc}"
            version.sync_status = "failed"
        finally:
            finished = datetime.now(timezone.utc)
            job.finished_at = finished
            version.sync_duration = (finished - job.started_at).total_seconds()
            session.commit()
            if engine is not None:
                engine.dispose()
