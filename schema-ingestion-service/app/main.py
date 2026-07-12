"""FastAPI application entry point."""
import structlog
from fastapi import FastAPI
from sqlalchemy import text

from app.api import jobs, metadata, sources
from app.db import get_engine

structlog.configure(processors=[
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.add_log_level,
    structlog.processors.JSONRenderer(),
])
log = structlog.get_logger()

app = FastAPI(
    title="Schema Ingestion & Semantic Metadata Service",
    version="0.1.0",
    description="Module 1 of the conversational analytics platform: connects to customer "
                "databases, ingests and profiles schemas, detects relationships, classifies "
                "dimensions/measures, and stores reviewable metadata.",
)
app.include_router(sources.router)
app.include_router(jobs.router)
app.include_router(metadata.router)


@app.get("/health", tags=["ops"])
def health() -> dict:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "metadata_db": "up"}
    except Exception as exc:
        log.error("health_check_failed", error=str(exc))
        return {"status": "degraded", "metadata_db": "down"}
