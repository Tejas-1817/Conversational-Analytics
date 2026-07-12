"""Pydantic DTOs for the REST API. Credentials go in and are never returned."""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DataSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: Literal["postgres", "mysql", "snowflake", "bigquery"]
    host: str
    port: int | None = None
    database_name: str
    username: str
    password: str = Field(repr=False)  # encrypted immediately; never persisted or logged in plain text
    options: dict = Field(default_factory=dict)


class DataSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    type: str
    host: str | None
    port: int | None
    database_name: str
    username: str
    status: str
    last_ingested_at: datetime | None
    # deliberately no credentials field


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source_id: uuid.UUID
    stage: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    stats: dict
    error: str | None


class ColumnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    column_name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool
    business_name: str | None
    description: str | None
    synonyms: list[str]
    role: str
    aggregation: str | None
    additivity: str
    profile: dict
    status: str


class TableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    schema_name: str
    table_name: str
    business_name: str | None
    description: str | None
    grain: str | None
    row_count: int | None
    is_active: bool
    status: str


class RelationshipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    from_column_id: uuid.UUID
    to_column_id: uuid.UUID
    cardinality: str
    source: str
    confidence: float
    evidence: dict
    status: str


class ReviewRequest(BaseModel):
    """Approve / edit / reject a metadata item."""
    action: Literal["approve", "reject", "needs_clarification", "edit"]
    actor: str = Field(min_length=1, description="Who is reviewing (email/username)")
    # Optional edits applied when action == 'edit' (or alongside approve)
    business_name: str | None = None
    description: str | None = None
    grain: str | None = None
    synonyms: list[str] | None = None
    role: Literal["dimension", "measure", "key", "attribute", "unknown"] | None = None
    aggregation: str | None = None
    additivity: Literal["additive", "semi_additive", "non_additive", "not_applicable"] | None = None
    cardinality: str | None = None
