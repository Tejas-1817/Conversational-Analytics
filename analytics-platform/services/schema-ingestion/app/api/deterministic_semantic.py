"""Deterministic Semantic Layer REST API endpoints.

Exposes endpoints for generating, fetching, regenerating, and reviewing
deterministic draft semantic objects (Tables, Columns, Relationships,
Dimensions, Metrics, Time Dimensions, and Join Paths).
"""
from typing import Any, Dict

import structlog
from fastapi import APIRouter

from app.semantic_engine.deterministic_semantic_generator import DeterministicSemanticGenerator

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/semantic-layer", tags=["deterministic-semantic-layer"])

generator = DeterministicSemanticGenerator()


@router.post("/generate")
@router.post("/schema/generate")
@router.post("/semantic/generate")
def generate_semantic_layer() -> Dict[str, Any]:
    """Trigger deterministic generation of draft semantic layer from connected DB."""
    return generator.generate_draft_semantic_layer(force_regenerate=False)


@router.post("/regenerate")
@router.post("/schema/regenerate")
@router.post("/semantic/regenerate")
def regenerate_semantic_layer() -> Dict[str, Any]:
    """Force re-inspection and deterministic regeneration of draft semantic layer."""
    return generator.generate_draft_semantic_layer(force_regenerate=True)


@router.get("")
def get_semantic_layer_summary() -> Dict[str, Any]:
    """Retrieve full summary of draft semantic layer objects."""
    return generator.generate_draft_semantic_layer(force_regenerate=False)


@router.get("/status")
def get_semantic_layer_status() -> Dict[str, Any]:
    """Get current status, timestamp, and entity counts of the draft semantic layer."""
    summary = generator.generate_draft_semantic_layer(force_regenerate=False)
    return {
        "database_name": summary.get("database_name"),
        "status": summary.get("status"),
        "generated_at": summary.get("generated_at"),
        "table_count": summary.get("table_count"),
        "column_count": summary.get("column_count"),
        "relationship_count": summary.get("relationship_count"),
        "dimension_count": summary.get("dimension_count"),
        "metric_count": summary.get("metric_count"),
        "time_dimension_count": summary.get("time_dimension_count"),
        "join_path_count": summary.get("join_path_count"),
    }


@router.get("/dimensions")
def get_dimensions() -> Dict[str, Any]:
    """List candidate draft dimensions."""
    summary = generator.generate_draft_semantic_layer(force_regenerate=False)
    return {
        "database_name": summary.get("database_name"),
        "status": summary.get("status"),
        "dimensions": summary.get("dimensions", []),
        "time_dimensions": summary.get("time_dimensions", [])
    }


@router.get("/metrics")
def get_metrics() -> Dict[str, Any]:
    """List candidate draft metrics."""
    summary = generator.generate_draft_semantic_layer(force_regenerate=False)
    return {
        "database_name": summary.get("database_name"),
        "status": summary.get("status"),
        "metrics": summary.get("metrics", [])
    }


@router.get("/relationships")
def get_relationships() -> Dict[str, Any]:
    """List candidate draft relationships and join paths."""
    summary = generator.generate_draft_semantic_layer(force_regenerate=False)
    return {
        "database_name": summary.get("database_name"),
        "status": summary.get("status"),
        "relationships": summary.get("relationships", []),
        "join_paths": summary.get("join_paths", [])
    }
