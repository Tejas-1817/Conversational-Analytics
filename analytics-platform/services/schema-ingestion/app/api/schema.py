from typing import Optional
import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.semantic_engine.deterministic_semantic_generator import DeterministicSemanticGenerator
from app.services.dynamic_schema_service import schema_service

log = structlog.get_logger(__name__)
router = APIRouter(tags=["schema"])

semantic_generator = DeterministicSemanticGenerator()


class SchemaMetadataResponse(BaseModel):
    database_name: str
    status: str
    generated_at: str
    table_count: int
    column_count: int
    relationship_count: int
    dimension_count: Optional[int] = 0
    metric_count: Optional[int] = 0
    time_dimension_count: Optional[int] = 0
    join_path_count: Optional[int] = 0
    # Backward compatibility fields for legacy callers
    schema_name: Optional[str] = None
    last_updated: Optional[str] = None


@router.get("/schema/metadata", response_model=SchemaMetadataResponse)
@router.get("/semantic/schema-metadata", response_model=SchemaMetadataResponse)
@router.get("/api/v1/schema/metadata", response_model=SchemaMetadataResponse)
def get_schema_metadata():
    """Retrieve metadata for the dynamically introspected PostgreSQL database schema."""
    try:
        data = semantic_generator.generate_draft_semantic_layer(force_regenerate=False)
        return SchemaMetadataResponse(
            database_name=data["database_name"],
            status=data["status"],
            generated_at=data["generated_at"],
            table_count=data["table_count"],
            column_count=data["column_count"],
            relationship_count=data["relationship_count"],
            dimension_count=data.get("dimension_count", 0),
            metric_count=data.get("metric_count", 0),
            time_dimension_count=data.get("time_dimension_count", 0),
            join_path_count=data.get("join_path_count", 0),
            schema_name=data["database_name"],
            last_updated=data["generated_at"]
        )
    except Exception as e:
        log.error("schema_metadata_fetch_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract database schema metadata: {e}"
        )


@router.post("/schema/generate", response_model=SchemaMetadataResponse)
@router.post("/api/v1/schema/generate", response_model=SchemaMetadataResponse)
def generate_schema():
    """Automatically inspect the connected database and generate the complete Draft Semantic Layer."""
    try:
        data = semantic_generator.generate_draft_semantic_layer(force_regenerate=True)
        return SchemaMetadataResponse(
            database_name=data["database_name"],
            status=data["status"],
            generated_at=data["generated_at"],
            table_count=data["table_count"],
            column_count=data["column_count"],
            relationship_count=data["relationship_count"],
            dimension_count=data.get("dimension_count", 0),
            metric_count=data.get("metric_count", 0),
            time_dimension_count=data.get("time_dimension_count", 0),
            join_path_count=data.get("join_path_count", 0),
            schema_name=data["database_name"],
            last_updated=data["generated_at"]
        )
    except Exception as e:
        log.error("schema_generation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate dynamic database semantic layer: {e}"
        )


@router.post("/schema/refresh", response_model=SchemaMetadataResponse)
@router.post("/api/v1/schema/refresh", response_model=SchemaMetadataResponse)
def refresh_schema():
    """Force re-introspection of the connected PostgreSQL database and update semantic layer cache."""
    try:
        data = semantic_generator.generate_draft_semantic_layer(force_regenerate=True)
        return SchemaMetadataResponse(
            database_name=data["database_name"],
            status=data["status"],
            generated_at=data["generated_at"],
            table_count=data["table_count"],
            column_count=data["column_count"],
            relationship_count=data["relationship_count"],
            dimension_count=data.get("dimension_count", 0),
            metric_count=data.get("metric_count", 0),
            time_dimension_count=data.get("time_dimension_count", 0),
            join_path_count=data.get("join_path_count", 0),
            schema_name=data["database_name"],
            last_updated=data["generated_at"]
        )
    except Exception as e:
        log.error("schema_refresh_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh dynamic database semantic layer: {e}"
        )
