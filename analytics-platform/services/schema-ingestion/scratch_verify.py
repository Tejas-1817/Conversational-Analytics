import sys
sys.path.insert(0, r"c:\Users\Admin\Downloads\Analytics Tool\Analytics Tool\analytics-platform\services\schema-ingestion")

from app.db import session_scope
from app.models import DataSource, IngestionJob
from app.ingestion.pipeline import run_pipeline
import uuid

with session_scope() as session:
    ds = session.query(DataSource).first()
    
    # Reset last_ingested_at to force semantic generation
    ds.last_ingested_at = None
    
    # Create job manually
    job = IngestionJob(source_id=ds.id)
    session.add(job)
    session.commit()
    
    job_id = str(job.id)
    source_id = str(ds.id)
    print(f"Running pipeline for job {job_id}...")

# Run synchronously
run_pipeline(job_id, source_id)

with session_scope() as session:
    job = session.query(IngestionJob).get(uuid.UUID(job_id))
    print(f"\nFinal Job Status: {job.status}")
    
    # Verify JobOut schema serialization
    from app.schemas import JobOut
    job_out = JobOut.model_validate(job)
    print("\nAPI Response Payload:")
    print(job_out.model_dump_json(indent=2))
