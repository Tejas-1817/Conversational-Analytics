import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict


class SemanticMetricCreate(BaseModel):
    name: str
    business_name: Optional[str] = None
    description: Optional[str] = None
    is_calculated: bool = False
    aggregation_type: str = "CUSTOM"
    expression: str
    source_table_id: Optional[uuid.UUID] = None
    source_column_id: Optional[uuid.UUID] = None
    owner: Optional[str] = None

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
    change_reason: Optional[str] = None

class SemanticDimensionCreate(BaseModel):
    business_name: str
    description: Optional[str] = None
    source_table_id: Optional[uuid.UUID] = None
    source_column_id: Optional[uuid.UUID] = None
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
    owner: Optional[str] = None

class BusinessGlossaryOut(BusinessGlossaryCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    status: str
