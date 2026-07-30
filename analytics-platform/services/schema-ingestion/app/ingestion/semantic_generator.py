"""Stage 5 — AI-Powered Semantic Layer Generation.

Executes a chunked workflow to generate a complete enterprise Semantic Layer
from the raw database schemas and profiling data.
"""
import uuid

import structlog
from sqlalchemy.orm import Session

from app.models import (
    BusinessGlossary,
    DataSource,
    SemanticDimension,
    SemanticJoin,
    SemanticMetric,
    SemanticModel,
    TableMeta,
)
from app.semantic.generation_service import SemanticGenerationService
from app.semantic.graph_validator import SemanticGraphValidator
from app.semantic.version_manager import SemanticVersionManager

log = structlog.get_logger()


def needs_full_regeneration(has_active_model: bool, ai_entity_count: int) -> bool:
    """Return whether a source lacks a usable AI-generated semantic baseline.

    A prior failed generation can still leave an active version containing only
    manually seeded objects.  Incremental ingestion must not treat that state
    as a complete semantic layer, otherwise all future runs skip generation.
    """
    return not has_active_model or ai_entity_count == 0


def run_semantic_generation(session: Session, source: DataSource, metadata_version_id: uuid.UUID) -> dict:
    """Executes chunked/incremental semantic generation."""
    log.info("semantic_generation_started", source=source.name)

    active_model = session.query(SemanticModel).filter_by(source_id=source.id, is_active=True).first()
    ai_entity_count = 0
    if active_model:
        ai_entity_count = sum(
            session.query(entity.id)
            .filter_by(semantic_model_id=active_model.id, generation_source="AI")
            .count()
            for entity in (SemanticMetric, SemanticDimension, SemanticJoin, BusinessGlossary)
        )
    force_full_regeneration = needs_full_regeneration(active_model is not None, ai_entity_count)

    # 1. Gather tables incrementally, except when no usable AI model exists.
    if source.last_ingested_at and not force_full_regeneration:
        tables = session.query(TableMeta).filter(
            TableMeta.source_id == source.id,
            TableMeta.is_active.is_(True),
            TableMeta.updated_at >= source.last_ingested_at
        ).all()
    else:
        tables = session.query(TableMeta).filter_by(source_id=source.id, is_active=True).all()

    if force_full_regeneration:
        log.info(
            "semantic_generation_full_regeneration_required",
            source=source.name,
            has_active_model=active_model is not None,
            ai_entity_count=ai_entity_count,
        )

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
        from app.config import get_settings
        settings = get_settings()
        max_workers = 3 if settings.llm_provider.lower() == "ollama" else 3
        
        tbl_metrics, tbl_warnings = SemanticGenerationService.generate_for_tables(
            session, tables, source.tenant_id, semantic_model.id, max_workers=max_workers
        )
        if tbl_metrics:
            for k, v in tbl_metrics.items():
                if k in summary_metrics:
                    summary_metrics[k] += v
        all_warnings.extend(tbl_warnings)
    except Exception as e:
        log.error("table_enrichment_failed", source=source.name, error=str(e))

    try:
        glb_metrics, glb_warnings = SemanticGenerationService.generate_global(session, source.id, semantic_model.id)
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
