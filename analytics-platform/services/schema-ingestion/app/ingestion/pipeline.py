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
from app.ingestion.schema_export import export_schema_snapshot
from app.ingestion.semantic_generator import run_semantic_generation
from app.models import DataSource, IngestionJob, MetadataVersion

log = structlog.get_logger()


def run_pipeline(job_id: str, source_id: str) -> None:
    """RQ entry point for automated 5-stage schema extraction & registry pipeline."""
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
        stats: dict = {}
        try:
            # Stage 1: Connection Validation
            job.stage = "Connection Validation"
            session.commit()
            log.info("stage_started", stage="Connection Validation", source=source.name)
            
            engine = build_engine(source)
            from app.connectors.factory import test_connection, verify_read_only
            test_connection(engine)
            verify_read_only(engine, source.type)
            stats["connection_validation"] = {"status": "succeeded", "database": source.database_name}
            job.stats = dict(stats)
            session.commit()
            log.info("stage_finished", stage="Connection Validation", status="succeeded")

            # Stage 2: Schema Extraction
            job.stage = "Schema Extraction"
            session.commit()
            log.info("stage_started", stage="Schema Extraction", source=source.name)
            
            intro_res = run_introspection(session, source, engine)
            stats["schema_extraction"] = intro_res
            job.stats = dict(stats)
            session.commit()
            log.info("stage_finished", stage="Schema Extraction", **intro_res)

            # Stage 3: Schema File Generation & Storage
            job.stage = "Schema File Generation"
            session.commit()
            log.info("stage_started", stage="Schema File Generation", source=source.name)
            
            from app.ingestion.schema_export import export_human_readable_schema
            export_res = export_human_readable_schema(session, source)
            stats["schema_file_generation"] = export_res
            job.stats = dict(stats)
            session.commit()
            log.info("stage_finished", stage="Schema File Generation", **export_res)

            # Stage 4: Schema Registration & Active Activation
            job.stage = "Schema Registration"
            session.commit()
            log.info("stage_started", stage="Schema Registration", source=source.name)
            
            from app.models import SchemaRegistry
            active_reg = session.query(SchemaRegistry).filter_by(source_id=source.id, is_active=True).first()
            stats["schema_registration"] = {
                "status": "succeeded",
                "active_version": active_reg.schema_version if active_reg else 1,
                "file_path": active_reg.file_path if active_reg else ""
            }
            job.stats = dict(stats)
            session.commit()
            log.info("stage_finished", stage="Schema Registration", status="succeeded")

            # Stage 5: Completed
            job.stage = "Completed"
            job.status = "succeeded"
            version.sync_status = "succeeded"
            source.status = "connected"
            source.last_ingested_at = datetime.now(timezone.utc)
            session.commit()
            log.info("pipeline_completed_successfully", source=source.name)

        except Exception as exc:
            log.exception("new_pipeline_failed", source=source.name)
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
