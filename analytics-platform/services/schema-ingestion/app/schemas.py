"""Pydantic DTOs for the REST API. Credentials go in and are never returned."""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, SecretStr


DatabaseType = Literal["postgres", "mysql", "mssql"]


class ConnectionOptions(BaseModel):
    include_schemas: list[str] = Field(default_factory=list)
    table_blocklist: list[str] = Field(default_factory=list)
    require_tls: bool = True
    connect_timeout_seconds: int = Field(default=10, ge=1, le=30)


class DataSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)

    type: DatabaseType
    host: str = Field(min_length=1, max_length=253)
    port: int = Field(ge=1, le=65535)
    database_name: str = Field(min_length=1, max_length=128)
    username: str = Field(min_length=1, max_length=128)
    password: SecretStr

    ssl_mode: Literal[
        "require",
        "verify-ca",
        "verify-full",
    ] = "verify-full"
    options: ConnectionOptions = Field(
        default_factory=ConnectionOptions
    )

class ExcelSheetOverride(BaseModel):
    table_name: str | None = None
    header_row: int = 0
    include: bool = True
    forward_fill_columns: list[str] | None = None


class ExcelSheetPreview(BaseModel):
    sheet_name: str
    suggested_table_name: str
    row_count: int
    column_names: list[str]
    suggested_header_row: int = 0
    preview_rows: list[dict] = []
    is_empty: bool = False
    warning: str | None = None


class ExcelPreviewResponse(BaseModel):
    temp_file_id: str
    filename: str
    sheets: list[ExcelSheetPreview]


class ExcelSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    temp_file_id: str
    sheet_overrides: dict[str, ExcelSheetOverride] = Field(default_factory=dict)
    options: dict = Field(default_factory=dict)



class DataSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    type: str
    host: str | None = None
    port: int | None = None
    database_name: str | None = None
    username: str | None = None
    file_path: str | None = None
    original_upload_path: str | None = None
    status: str

    connection_status: str
    schema_status: str
    embedding_status: str
    last_connection_test_at: datetime | None
    last_ingested_at: datetime | None

    last_ingested_at: datetime | None = None

    # deliberately no credentials field


class JobWarning(BaseModel):
    stage: str
    table: str | None = None
    provider: str | None = None
    error_type: str
    message: str
    recoverable: bool
    timestamp: str
    attempt: int = 1

class JobSummary(BaseModel):
    tables_processed: int = 0
    tables_succeeded: int = 0
    tables_failed: int = 0
    llm_requests: int = 0
    llm_successes: int = 0
    llm_failures: int = 0
    generated_metrics: int = 0
    generated_dimensions: int = 0
    generated_entities: int = 0
    generated_relationships: int = 0
    warnings_count: int = 0

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
    
    @computed_field
    def warnings(self) -> list[JobWarning]:
        return self.stats.get("warnings", [])
        
    @computed_field
    def summary(self) -> JobSummary | None:
        if "summary" in self.stats:
            return JobSummary(**self.stats["summary"])
        return None


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
    actor: str | None = Field(default=None, description="Who is reviewing (email/username)")
    # Optional edits applied when action == 'edit' (or alongside approve)
    business_name: str | None = None
    description: str | None = None
    grain: str | None = None
    synonyms: list[str] | None = None
    role: Literal["dimension", "measure", "key", "attribute", "unknown"] | None = None
    aggregation: str | None = None
    additivity: Literal["additive", "semi_additive", "non_additive", "not_applicable"] | None = None
    cardinality: str | None = None
