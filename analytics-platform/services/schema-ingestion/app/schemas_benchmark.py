from typing import List, Optional
import uuid
from pydantic import BaseModel, Field

class BenchmarkTestCase(BaseModel):
    id: str = Field(description="Unique string identifier for the test case")
    question: str = Field(description="The natural language question to test")
    domain: str = Field(description="The domain category, e.g., 'HR', 'Sales'")
    expected_semantic_objects: List[str] = Field(default_factory=list, description="List of expected metric or dimension names")
    expected_sql_structure: Optional[List[str]] = Field(default=None, description="Keywords expected in SQL, e.g., 'GROUP BY'")
    expected_columns: Optional[List[str]] = Field(default=None, description="Expected resulting columns")

class TestCaseResult(BaseModel):
    test_case_id: str
    question: str
    domain: str
    
    # Semantic Retrieval Metrics
    retrieval_precision: float
    retrieval_recall: float
    
    # Generative Metrics
    generated_sql: Optional[str]
    sql_is_valid: bool
    hallucination_detected: bool
    safety_violation_detected: bool
    
    # Execution Metrics
    execution_success: bool
    execution_error: Optional[str] = None
    returned_columns: List[str] = Field(default_factory=list)
    schema_matched: bool
    
    # Confidence Metrics
    reported_confidence: float
    calibration_error: float
    
    # Performance Metrics (ms)
    total_latency_ms: int

class BenchmarkReport(BaseModel):
    run_id: str
    total_test_cases: int
    success_rate: float
    
    avg_retrieval_precision: float
    avg_retrieval_recall: float
    
    hallucination_rate: float
    safety_violation_rate: float
    sql_validity_rate: float
    execution_success_rate: float
    schema_match_rate: float
    
    avg_calibration_error: float
    
    avg_latency_ms: int
    p95_latency_ms: int
    
    failure_reasons: dict[str, int] = Field(default_factory=dict, description="Counts of failure reasons")
    results: List[TestCaseResult] = Field(default_factory=list)

class BenchmarkRunRequest(BaseModel):
    tenant_id: uuid.UUID
    dataset_name: str = Field(default="all", description="Which dataset to run, e.g., 'HR', 'Sales', or 'all'")
