import uuid

from pydantic import BaseModel, ConfigDict


class SemanticMetricCreate(BaseModel):
    name: str
    business_name: str | None = None
    description: str | None = None
    is_calculated: bool = False
    aggregation_type: str = "CUSTOM"
    expression: str
    source_table_id: uuid.UUID | None = None
    source_column_id: uuid.UUID | None = None
    owner: str | None = None

class SemanticMetricOut(SemanticMetricCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    status: str
    version: int

class MetricVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    metric_id: uuid.UUID
    version: int
    snapshot: dict
    created_by: str
    change_reason: str | None = None

class SemanticDimensionCreate(BaseModel):
    business_name: str
    description: str | None = None
    source_table_id: uuid.UUID | None = None
    source_column_id: uuid.UUID | None = None
    data_type: str
    is_time_dimension: bool = False
    time_granularity: str = "NONE"

class SemanticDimensionOut(SemanticDimensionCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    visibility: str
    status: str
    version: int

class SemanticJoinCreate(BaseModel):
    left_table_id: uuid.UUID
    right_table_id: uuid.UUID
    join_condition: str
    join_type: str = "LEFT"
    cardinality: str = "many_to_one"
    confidence: float = 1.0

class SemanticJoinOut(SemanticJoinCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    status: str
    version: int

class BusinessGlossaryCreate(BaseModel):
    term: str
    business_definition: str
    owner: str | None = None

class BusinessGlossaryOut(BusinessGlossaryCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    status: str
