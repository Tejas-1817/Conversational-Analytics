"""Stage 5 — AI-Powered Semantic Layer Generation.

Executes a chunked workflow to generate a complete enterprise Semantic Layer
from the raw database schemas and profiling data.
"""
import json
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models import (
    DataSource,
    SemanticModel,
    TableMeta,
)
from app.semantic.enrichment_service import SemanticEnrichmentService
from app.semantic.version_manager import SemanticVersionManager
from app.semantic.graph_validator import SemanticGraphValidator

log = structlog.get_logger()

def run_semantic_generation(session: Session, source: DataSource, metadata_version_id: uuid.UUID) -> dict:
    """Executes chunked/incremental semantic generation."""
    log.info("semantic_generation_started", source=source.name)

    # Determine next semantic version
    max_semantic = session.query(SemanticModel).filter_by(source_id=source.id).order_by(SemanticModel.semantic_version.desc()).first()
    new_version = (max_semantic.semantic_version + 1) if max_semantic else 1

    # 1. Gather Tables for Incremental Generation
    # If source.last_ingested_at is None, it's the first run, process all.
    # Otherwise, only process tables updated since the last ingestion.
    if source.last_ingested_at:
        tables = session.query(TableMeta).filter(
            TableMeta.source_id == source.id,
            TableMeta.is_active == True,
            TableMeta.updated_at >= source.last_ingested_at
        ).all()
    else:
        tables = session.query(TableMeta).filter_by(source_id=source.id, is_active=True).all()

    if not tables:
        return {"status": "skipped", "reason": "no_changed_tables"}

    changed_table_ids = [t.id for t in tables]

    # Stage 1: Initialize New Version
    semantic_model = SemanticVersionManager.initialize_version(session, source.id, source.tenant_id, metadata_version_id)
    
    # Stage 2: Copy-on-Write (Clone unchanged entities)
    old_active = session.query(SemanticModel).filter_by(source_id=source.id, is_active=True).first()
    if old_active:
        SemanticVersionManager.clone_unchanged_entities(session, old_active.id, semantic_model.id, changed_table_ids)

    # Stage 3: AI Enrichment (Incremental tables + Global)
    for t in tables:
        try:
            SemanticEnrichmentService.enrich_table(session, t.id, source.tenant_id, semantic_model.id)
        except Exception as e:
            log.error("table_enrichment_failed", table=t.table_name, error=str(e))
            continue

    try:
        SemanticEnrichmentService.enrich_global(session, source.id, semantic_model.id)
    except Exception as e:
        log.error("global_enrichment_failed", source=source.name, error=str(e))

    # Stage 4: Validate Graph
    is_valid = SemanticGraphValidator.validate(session, semantic_model.id)
    if not is_valid:
        semantic_model.generation_status = "FAILED"
        session.commit()
        log.error("semantic_graph_validation_failed", semantic_model_id=str(semantic_model.id))
        return {"status": "failed", "reason": "graph_validation_failed"}

    # Stage 5: Atomic Promotion
    SemanticVersionManager.promote_version(session, source.id, semantic_model.id)

    log.info("semantic_generation_completed", semantic_model_id=str(semantic_model.id))
    return {"status": "success", "semantic_version": semantic_model.semantic_version}
