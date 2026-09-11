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
            # Stage 0: Excel Materialization (only for type='excel')
            if source.type == "excel":
                job.stage = "Excel Materialization"
                session.commit()
                log.info("stage_started", stage="Excel Materialization", source=source.name)

                from app.config import get_settings
                from app.ingestion.excel_ingestor import materialize_excel_to_sqlite
                from pathlib import Path
                settings = get_settings()

                target_sqlite_dir = Path(settings.excel_sqlite_dir) / str(source.tenant_id) / str(source.id)
                target_sqlite_dir.mkdir(parents=True, exist_ok=True)
                target_sqlite_path = (target_sqlite_dir / "materialized.db").resolve().as_posix()

                upload_src = source.original_upload_path or source.file_path
                sheet_overrides = source.options.get("sheet_overrides") if source.options else None
                mat_stats = materialize_excel_to_sqlite(
                    upload_path=upload_src,
                    sqlite_path=target_sqlite_path,
                    sheet_overrides=sheet_overrides
                )
                source.file_path = target_sqlite_path
                stats["excel_materialization"] = mat_stats
                job.stats = dict(stats)
                session.commit()
                log.info("stage_finished", stage="Excel Materialization", **mat_stats)

            # Stage 1: Connection Validation
            job.stage = "Connection Validation"
            session.commit()
            log.info("stage_started", stage="Connection Validation", source=source.name)
            
            engine = build_engine(source)
            from app.connectors.factory import test_connection, verify_read_only
            test_connection(engine)
            verify_read_only(engine, source.type)
            stats["connection_validation"] = {"status": "succeeded", "database": source.database_name or "sqlite"}
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

            # Stage 2b: Relationship Detection (naming & value overlap heuristic)
            job.stage = "Relationship Detection"
            session.commit()
            log.info("stage_started", stage="Relationship Detection", source=source.name)
            try:
                rel_res = run_relationship_detection(session, source, engine)
                stats["relationship_detection"] = rel_res
                job.stats = dict(stats)
                session.commit()
                log.info("stage_finished", stage="Relationship Detection", **rel_res)
            except Exception as rel_exc:
                log.warning("relationship_detection_failed_non_fatal", error=str(rel_exc))
                stats["relationship_detection"] = {"status": "skipped", "error": str(rel_exc)}

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
            import traceback
            tb = traceback.format_exc()
            log.error("new_pipeline_failed", source=source.name, stage=job.stage, error=str(exc), error_type=type(exc).__name__, traceback=tb)
            print(f"\n[PIPELINE ERROR] Stage '{job.stage}' failed for source '{source.name}':\n{tb}\n", flush=True)
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
