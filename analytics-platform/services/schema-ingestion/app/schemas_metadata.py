import uuid
from datetime import datetime

from pydantic import BaseModel


class IndexMetaResponse(BaseModel):
    id: uuid.UUID
    index_name: str
    column_names: list[str]
    is_unique: bool

    class Config:
        from_attributes = True


class ColumnMetaResponse(BaseModel):
    id: uuid.UUID
    column_name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool
    role: str
    aggregation: str | None = None
    additivity: str
    description: str | None = None

    class Config:
        from_attributes = True


class TableMetaResponse(BaseModel):
    id: uuid.UUID
    schema_name: str
    table_name: str
    description: str | None = None
    row_count: int | None = None
    is_active: bool

    class Config:
        from_attributes = True


class TableMetaDetailResponse(TableMetaResponse):
    columns: list[ColumnMetaResponse]
    indexes: list[IndexMetaResponse]


class SyncRequest(BaseModel):
    source_id: uuid.UUID


class SyncStatusResponse(BaseModel):
    version_number: int
    sync_status: str
    sync_duration: float | None = None
    created_at: datetime

    class Config:
        from_attributes = True
