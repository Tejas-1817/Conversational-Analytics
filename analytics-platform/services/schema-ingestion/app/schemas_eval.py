import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

# --- Inputs for Datasets ---

class EvaluationDatasetCreate(BaseModel):
    question: str
    difficulty: str | None = None
    tags: list[str] = []
    expected_intent: dict[str, Any] | None = None
    expected_plan: dict[str, Any] | None = None
    expected_sql: str | None = None
    expected_result: dict[str, Any] | None = None
    expected_chart: str | None = None

class EvaluationDatasetOut(EvaluationDatasetCreate):
    id: uuid.UUID
    collection_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- Inputs for Collections ---

class BenchmarkCollectionCreate(BaseModel):
    name: str
    description: str | None = None
    domain: str | None = None

class BenchmarkCollectionOut(BenchmarkCollectionCreate):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    created_by: str
    datasets: list[EvaluationDatasetOut] = []
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

    generated_intent: dict[str, Any] | None = None
    generated_plan: dict[str, Any] | None = None
    generated_sql: str | None = None
    generated_result: dict[str, Any] | None = None
    generated_chart: str | None = None
    generated_answer: str | None = None

    execution_time_ms: int | None = None
    error: str | None = None

    intent_score: float | None = None
    plan_score: float | None = None
    sql_score: float | None = None
    result_score: float | None = None
    chart_score: float | None = None
    nl_score: float | None = None

    reliability_score: float | None = None
    is_pass: bool | None = None
    failure_reasons: list[str] = []

    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- Outputs for Runs ---

class EvaluationRunOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    collection_id: uuid.UUID
    status: str
    overall_score: float | None = None
    pass_rate: float | None = None
    avg_latency_ms: int | None = None
    error_rate: float | None = None
    started_at: datetime
    finished_at: datetime | None = None
    triggered_by: str
    model_config = ConfigDict(from_attributes=True)

class EvaluationRunDetailedOut(EvaluationRunOut):
    results: list[EvaluationResultOut] = []
