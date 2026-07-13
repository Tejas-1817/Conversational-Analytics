from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict
from datetime import datetime
import uuid

# --- Inputs for Datasets ---

class EvaluationDatasetCreate(BaseModel):
    question: str
    difficulty: Optional[str] = None
    tags: List[str] = []
    expected_intent: Optional[Dict[str, Any]] = None
    expected_plan: Optional[Dict[str, Any]] = None
    expected_sql: Optional[str] = None
    expected_result: Optional[Dict[str, Any]] = None
    expected_chart: Optional[str] = None

class EvaluationDatasetOut(EvaluationDatasetCreate):
    id: uuid.UUID
    collection_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- Inputs for Collections ---

class BenchmarkCollectionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    domain: Optional[str] = None

class BenchmarkCollectionOut(BenchmarkCollectionCreate):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    created_by: str
    datasets: List[EvaluationDatasetOut] = []
    model_config = ConfigDict(from_attributes=True)

class BenchmarkCollectionListOut(BenchmarkCollectionCreate):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    created_by: str
    model_config = ConfigDict(from_attributes=True)

# --- Outputs for Results ---

class EvaluationResultOut(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    dataset_id: uuid.UUID
    
    generated_intent: Optional[Dict[str, Any]] = None
    generated_plan: Optional[Dict[str, Any]] = None
    generated_sql: Optional[str] = None
    generated_result: Optional[Dict[str, Any]] = None
    generated_chart: Optional[str] = None
    generated_answer: Optional[str] = None
    
    execution_time_ms: Optional[int] = None
    error: Optional[str] = None
    
    intent_score: Optional[float] = None
    plan_score: Optional[float] = None
    sql_score: Optional[float] = None
    result_score: Optional[float] = None
    chart_score: Optional[float] = None
    nl_score: Optional[float] = None
    
    reliability_score: Optional[float] = None
    is_pass: Optional[bool] = None
    failure_reasons: List[str] = []
    
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- Outputs for Runs ---

class EvaluationRunOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    collection_id: uuid.UUID
    status: str
    overall_score: Optional[float] = None
    pass_rate: Optional[float] = None
    avg_latency_ms: Optional[int] = None
    error_rate: Optional[float] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    triggered_by: str
    model_config = ConfigDict(from_attributes=True)

class EvaluationRunDetailedOut(EvaluationRunOut):
    results: List[EvaluationResultOut] = []
