import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db import get_session as get_db
from app.api.deps import get_current_user
from app.models import User, BenchmarkCollection, EvaluationDataset, EvaluationRun, EvaluationResult
from app.schemas_eval import (
    BenchmarkCollectionCreate,
    BenchmarkCollectionOut,
    BenchmarkCollectionListOut,
    EvaluationDatasetCreate,
    EvaluationDatasetOut,
    EvaluationRunOut,
    EvaluationRunDetailedOut
)
from app.engine.eval.runner import BenchmarkRunner

router = APIRouter(prefix="/eval", tags=["Evaluation"])

# --- Collections ---

@router.get("/collections", response_model=List[BenchmarkCollectionListOut])
def list_collections(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    collections = db.scalars(select(BenchmarkCollection).where(
        BenchmarkCollection.tenant_id == current_user.tenant_id
    )).all()
    return collections

@router.post("/collections", response_model=BenchmarkCollectionOut)
def create_collection(collection: BenchmarkCollectionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_collection = BenchmarkCollection(
        tenant_id=current_user.tenant_id,
        name=collection.name,
        description=collection.description,
        domain=collection.domain,
        created_by=current_user.email
    )
    db.add(db_collection)
    db.commit()
    db.refresh(db_collection)
    return db_collection

# --- Datasets ---

@router.post("/collections/{collection_id}/datasets", response_model=EvaluationDatasetOut)
def add_dataset(collection_id: uuid.UUID, dataset: EvaluationDatasetCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    collection = db.scalar(select(BenchmarkCollection).where(
        BenchmarkCollection.id == collection_id,
        BenchmarkCollection.tenant_id == current_user.tenant_id
    ))
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
        
    db_dataset = EvaluationDataset(
        collection_id=collection_id,
        question=dataset.question,
        difficulty=dataset.difficulty,
        tags=dataset.tags,
        expected_intent=dataset.expected_intent,
        expected_plan=dataset.expected_plan,
        expected_sql=dataset.expected_sql,
        expected_result=dataset.expected_result,
        expected_chart=dataset.expected_chart
    )
    db.add(db_dataset)
    db.commit()
    db.refresh(db_dataset)
    return db_dataset

# --- Runs ---

def run_benchmark_background(tenant_id: uuid.UUID, collection_id: uuid.UUID, triggered_by: str, db: Session):
    try:
        BenchmarkRunner.run_collection(db, tenant_id, collection_id, triggered_by)
    finally:
        db.close()

@router.post("/runs/{collection_id}", response_model=EvaluationRunOut)
def trigger_run(collection_id: uuid.UUID, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Run the benchmark synchronously for now to ensure it completes, 
    # but in a real app this should be enqueued via rq or background tasks.
    # We will just run it synchronously for simplicity of testing.
    run = BenchmarkRunner.run_collection(db, current_user.tenant_id, collection_id, current_user.email)
    return run

@router.get("/runs", response_model=List[EvaluationRunOut])
def list_runs(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    runs = db.scalars(select(EvaluationRun).where(
        EvaluationRun.tenant_id == current_user.tenant_id
    ).order_by(EvaluationRun.started_at.desc())).all()
    return runs

@router.get("/runs/{run_id}", response_model=EvaluationRunDetailedOut)
def get_run_details(run_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    run = db.scalar(select(EvaluationRun).where(
        EvaluationRun.id == run_id,
        EvaluationRun.tenant_id == current_user.tenant_id
    ))
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    return run
