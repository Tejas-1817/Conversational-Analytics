import uuid
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime

# --- LLM Structured Output Models ---

class RouterResult(BaseModel):
    route: Literal["analytics", "greeting", "conversation", "help", "unknown"] = Field(description="The classification route")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    reason: str = Field(description="Reason for the routing classification")

class NLUFilter(BaseModel):
    field: str
    operator: str = Field(description="One of: =, !=, >, <, >=, <=, IN, LIKE, BETWEEN")
    value: Any

class NLUIntent(BaseModel):
    intent: Literal["aggregate", "list", "clarify", "unknown"] = Field(default="unknown", description="The primary intent of the user")
    metric: Optional[str] = Field(default=None, description="The primary metric requested, e.g., 'Revenue', 'Sales', 'Active Users'")
    dimensions: List[str] = Field(default_factory=list, description="List of dimensions to group by, e.g., 'Region', 'Product'")
    filters: List[NLUFilter] = Field(default_factory=list, description="List of filters to apply")
    time_granularity: Optional[Literal["day", "week", "month", "quarter", "year"]] = Field(default=None)
    sort_by: Optional[str] = Field(default=None)
    sort_direction: Optional[Literal["ASC", "DESC"]] = Field(default=None)
    limit: Optional[int] = Field(default=None)

class QueryPlanFilter(BaseModel):
    column_id: uuid.UUID
    operator: str
    value: Any

class StructuredQueryPlan(BaseModel):
    metric_id: uuid.UUID
    dimension_ids: List[uuid.UUID] = Field(default_factory=list)
    filters: List[QueryPlanFilter] = Field(default_factory=list)
    time_granularity: Optional[str] = None
    sort_column_id: Optional[uuid.UUID] = None
    sort_direction: Optional[str] = None
    limit: Optional[int] = None

# --- API Request/Response Models ---

class ChatRequest(BaseModel):
    message: str

class ChatMessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    created_at: datetime
    route: Optional[str] = None
    trace: Optional[Dict[str, Any]] = None
    intent: Optional[Dict[str, Any]] = None
    query_plan: Optional[Dict[str, Any]] = None
    generated_sql: Optional[str] = None
    execution_time_ms: Optional[int] = None
    result_data: Optional[Dict[str, Any]] = None
    chart_recommendation: Optional[str] = None
    error: Optional[str] = None
    confidence_score: Optional[float] = None
    confidence_reason: Optional[str] = None

    class Config:
        from_attributes = True

class ConversationOut(BaseModel):
    id: uuid.UUID
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessageOut] = []

    class Config:
        from_attributes = True
