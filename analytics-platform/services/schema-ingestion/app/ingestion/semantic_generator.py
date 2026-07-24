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

    # Stage 3: AI Enrichment (Parallel Table + Global)
    all_warnings = []
    summary_metrics = {
        "tables_processed": len(tables),
        "tables_succeeded": 0,
        "tables_failed": 0,
        "llm_requests": 0,
        "llm_successes": 0,
        "llm_failures": 0,
        "generated_metrics": 0,
        "generated_dimensions": 0,
        "generated_entities": 0,
        "generated_relationships": 0,
        "warnings_count": 0
    }
    
    try:
        tbl_metrics, tbl_warnings = SemanticEnrichmentService.enrich_tables_parallel(session, tables, source.tenant_id, semantic_model.id)
        if tbl_metrics:
            for k, v in tbl_metrics.items():
                if k in summary_metrics:
                    summary_metrics[k] += v
        all_warnings.extend(tbl_warnings)
    except Exception as e:
        log.error("table_enrichment_failed", source=source.name, error=str(e))

    try:
        glb_metrics, glb_warnings = SemanticEnrichmentService.enrich_global(session, source.id, semantic_model.id)
        if glb_metrics:
            summary_metrics["llm_requests"] += glb_metrics.get("llm_requests", 0)
            summary_metrics["llm_successes"] += glb_metrics.get("llm_successes", 0)
            summary_metrics["llm_failures"] += glb_metrics.get("llm_failures", 0)
        all_warnings.extend(glb_warnings)
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

    # Calculate actual generated objects for metrics
    from app.models import SemanticMetric, SemanticDimension, BusinessGlossary, SemanticJoin
    num_metrics = session.query(SemanticMetric).filter_by(semantic_model_id=semantic_model.id).count()
    num_dims = session.query(SemanticDimension).filter_by(semantic_model_id=semantic_model.id).count()
    num_glossary = session.query(BusinessGlossary).filter_by(semantic_model_id=semantic_model.id).count()
    num_joins = session.query(SemanticJoin).filter_by(semantic_model_id=semantic_model.id).count()
    
    summary_metrics["generated_metrics"] = num_metrics
    summary_metrics["generated_dimensions"] = num_dims
    summary_metrics["generated_entities"] = num_metrics + num_dims + num_glossary
    summary_metrics["generated_relationships"] = num_joins
    summary_metrics["warnings_count"] = len(all_warnings)
    
    status_msg = "success"
    if summary_metrics["generated_entities"] == 0:
        status_msg = "succeeded_with_warnings"
        import datetime
        all_warnings.append({
            "stage": "semantic_generation",
            "table": None,
            "provider": "system",
            "error_type": "AI_GENERATION_FAILED",
            "message": "No semantic objects were generated because AI generation failed.",
            "recoverable": False,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "attempt": 1
        })
        summary_metrics["warnings_count"] = len(all_warnings)
        
    num_cols = sum(len(t.columns) for t in tables)
    log.info(
        "semantic_generation_completed",
        semantic_model_id=str(semantic_model.id),
        tables_count=len(tables),
        columns_count=num_cols,
        status=status_msg
    )
    return {
        "status": status_msg, 
        "semantic_version": semantic_model.semantic_version,
        "warnings": all_warnings,
        "summary": summary_metrics
    }

