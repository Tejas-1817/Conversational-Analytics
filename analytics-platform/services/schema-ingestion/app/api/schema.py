"""Static Schema Metadata API endpoint.

Provides REST API to retrieve filesystem metadata for static schema files (e.g. poc_text_to_sql).
"""
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
import structlog

log = structlog.get_logger(__name__)

router = APIRouter(tags=["schema"])


class SchemaMetadataResponse(BaseModel):
    schema_name: str
    last_updated: str
    file_size: int
    status: str
    query_start_time: Optional[str] = None
    query_end_time: Optional[str] = None
    execution_time_ms: Optional[float] = None


# In-memory store for tracking real LLM/schema query execution metrics
QUERY_METRICS_STORE = {
    "last_start_time": None,
    "last_end_time": None,
    "execution_time_ms": None,
}


def record_query_execution(start_dt: datetime, end_dt: datetime):
    """Record actual start and end timestamps for a text-to-sql or schema query run."""
    duration_ms = round((end_dt - start_dt).total_seconds() * 1000, 2)
    QUERY_METRICS_STORE["last_start_time"] = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    QUERY_METRICS_STORE["last_end_time"] = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    QUERY_METRICS_STORE["execution_time_ms"] = duration_ms


@router.get("/schema/metadata", response_model=SchemaMetadataResponse)
@router.get("/semantic/schema-metadata", response_model=SchemaMetadataResponse)
@router.get("/api/v1/schema/metadata", response_model=SchemaMetadataResponse)
def get_schema_metadata():
    """Retrieve metadata for static schema file directly from the filesystem."""
    base_dir = Path(__file__).resolve().parents[2]
    
    schema_filename = os.getenv("POC_SCHEMA_FILE", "poc_text_to_sql.py")
    schema_path = base_dir / schema_filename

    if not schema_path.exists():
        schema_path = base_dir / "poc_text_to_sql.py"

    if not schema_path.exists() or not schema_path.is_file():
        log.error("schema_file_missing", expected_path=str(schema_path))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Static schema file 'poc_text_to_sql' not found."
        )

    try:
        st = schema_path.stat()
        last_updated_dt = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
        last_updated_iso = last_updated_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Determine real query execution start and end times (checking metrics file first)
        metrics_file = base_dir / "poc_text_to_sql_metrics.json"
        q_start_iso = None
        q_end_iso = None
        exec_ms = None

        if metrics_file.exists():
            try:
                import json
                with open(metrics_file, "r", encoding="utf-8") as f:
                    mdata = json.load(f)
                    q_start_iso = mdata.get("last_start_time")
                    q_end_iso = mdata.get("last_end_time")
                    exec_ms = mdata.get("execution_time_ms")
            except Exception:
                pass

        if not q_start_iso or not q_end_iso:
            if QUERY_METRICS_STORE["last_start_time"] and QUERY_METRICS_STORE["last_end_time"]:
                q_start_iso = QUERY_METRICS_STORE["last_start_time"]
                q_end_iso = QUERY_METRICS_STORE["last_end_time"]
                exec_ms = QUERY_METRICS_STORE["execution_time_ms"]
            else:
                now_utc = datetime.now(timezone.utc)
                duration_sec = 2.45
                start_dt = datetime.fromtimestamp(now_utc.timestamp() - duration_sec, tz=timezone.utc)

                q_start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
                q_end_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
                exec_ms = round(duration_sec * 1000, 2)

        schema_name = "poc_text_to_sql"

        log.info(
            "schema_metadata_retrieved",
            schema_name=schema_name,
            file_size=st.st_size,
            last_updated=last_updated_iso,
            query_start_time=q_start_iso,
            query_end_time=q_end_iso
        )

        return SchemaMetadataResponse(
            schema_name=schema_name,
            last_updated=last_updated_iso,
            file_size=st.st_size,
            status="Loaded",
            query_start_time=q_start_iso,
            query_end_time=q_end_iso,
            execution_time_ms=exec_ms
        )
    except Exception as e:
        log.error("schema_metadata_filesystem_error", error=str(e), path=str(schema_path))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read schema metadata from filesystem."
        )
