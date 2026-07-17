import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

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
    intent: Literal["aggregate", "time_series", "comparison", "distribution", "top_n", "bottom_n", "trend", "list", "clarify", "unknown"] = Field(default="unknown", description="The primary intent of the user")
    metric: str | None = Field(default=None, description="The primary metric requested, e.g., 'Revenue', 'Sales', 'Active Users'")
    kpi: str | None = Field(default=None, description="The primary KPI requested, e.g., 'Net Profit Margin'")
    dimensions: list[str] = Field(default_factory=list, description="List of dimensions to group by, e.g., 'Region', 'Product'")
    filters: list[NLUFilter] = Field(default_factory=list, description="List of filters to apply")
    time_granularity: Literal["day", "week", "month", "quarter", "year"] | None = Field(default=None)
    time_intelligence: str | None = Field(default=None, description="E.g., 'YTD', 'MTD', 'Rolling 30 Days'")
    sort_by: str | None = Field(default=None)
    sort_direction: Literal["ASC", "DESC"] | None = Field(default=None)
    limit: int | None = Field(default=None)

class QueryPlanFilter(BaseModel):
    column_id: uuid.UUID
    operator: str
    value: Any

class LogicalQueryPlan(BaseModel):
    intent: str
    kpi_ids: list[uuid.UUID] = Field(default_factory=list)
    metric_ids: list[uuid.UUID] = Field(default_factory=list)
    dimension_ids: list[uuid.UUID] = Field(default_factory=list)
    filters: list[QueryPlanFilter] = Field(default_factory=list)
    time_granularity: str | None = None
    time_intelligence: str | None = None
    sort_column_id: uuid.UUID | None = None
    sort_direction: Literal["ASC", "DESC"] | None = None
    limit: int | None = None
    chart_recommendation: str | None = None
    confidence_score: float = Field(default=1.0)
    reasoning: str | None = None

# --- API Request/Response Models ---

class ChatRequest(BaseModel):
    message: str

class ChatMessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    intent: dict | None = None
    generated_sql: str | None = None
    result_data: dict | None = None
    error: str | None = None
    created_at: datetime
    route: str | None = None
    trace: dict[str, Any] | None = None
    intent: dict[str, Any] | None = None
    query_plan: dict[str, Any] | None = None
    generated_sql: str | None = None
    execution_time_ms: int | None = None
    result_data: dict[str, Any] | None = None
    chart_recommendation: str | None = None
    error: str | None = None
    confidence_score: float | None = None
    confidence_reason: str | None = None

    class Config:
        from_attributes = True

class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str | None = None
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageOut] = []

    class Config:
        from_attributes = True

class UserFeedbackCreate(BaseModel):
    is_positive: bool
    correction: str | None = None

class UserFeedbackOut(BaseModel):
    id: uuid.UUID
    message_id: uuid.UUID
    is_positive: bool
    correction: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True

class ApprovedExampleCreate(BaseModel):
    # Approval can be from an existing message, so we just pass message_id
    message_id: uuid.UUID

class ApprovedExampleOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    question: str
    generated_sql: str
    approved_by: uuid.UUID | None = None
    created_at: datetime

    class Config:
        from_attributes = True
