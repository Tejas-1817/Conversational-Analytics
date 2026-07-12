"""SQLAlchemy ORM models. Must stay in sync with migrations/001_init.sql (DDL is source of truth)."""
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, ForeignKey, Integer, LargeBinary,
    Numeric, Text, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, ENUM, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# Enum types already created by the DDL migration; create_type=False prevents ORM from re-creating them.
approval_status = ENUM("draft", "reviewed", "approved", "rejected", "needs_clarification",
                       name="approval_status", create_type=False)
column_role = ENUM("dimension", "measure", "key", "attribute", "unknown",
                   name="column_role", create_type=False)
additivity_type = ENUM("additive", "semi_additive", "non_additive", "not_applicable",
                       name="additivity_type", create_type=False)
rel_source = ENUM("declared_fk", "naming", "value_overlap", "llm",
                  name="rel_source", create_type=False)
job_status = ENUM("queued", "running", "succeeded", "failed",
                  name="job_status", create_type=False)
source_type = ENUM("postgres", "mysql", "snowflake", "bigquery",
                   name="source_type", create_type=False)


class DataSource(Base):
    __tablename__ = "data_sources"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(source_type, nullable=False)
    host: Mapped[str | None] = mapped_column(Text)
    port: Mapped[int | None] = mapped_column(Integer)
    database_name: Mapped[str] = mapped_column(Text, nullable=False)
    username: Mapped[str] = mapped_column(Text, nullable=False)
    credentials_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    options: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="registered")
    last_ingested_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)

    tables: Mapped[list["TableMeta"]] = relationship(back_populates="source", cascade="all, delete-orphan")


class TableMeta(Base):
    __tablename__ = "tables_meta"
    __table_args__ = (UniqueConstraint("source_id", "schema_name", "table_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=text("gen_random_uuid()"))
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False)
    schema_name: Mapped[str] = mapped_column(Text, nullable=False)
    table_name: Mapped[str] = mapped_column(Text, nullable=False)
    business_name: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    grain: Mapped[str | None] = mapped_column(Text)
    row_count: Mapped[int | None] = mapped_column(BigInteger)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    status: Mapped[str] = mapped_column(approval_status, nullable=False, server_default="draft")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_by: Mapped[str] = mapped_column(Text, nullable=False, server_default="system")

    source: Mapped[DataSource] = relationship(back_populates="tables")
    columns: Mapped[list["ColumnMeta"]] = relationship(back_populates="table", cascade="all, delete-orphan")


class ColumnMeta(Base):
    __tablename__ = "columns_meta"
    __table_args__ = (UniqueConstraint("table_id", "column_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=text("gen_random_uuid()"))
    table_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tables_meta.id", ondelete="CASCADE"), nullable=False)
    column_name: Mapped[str] = mapped_column(Text, nullable=False)
    ordinal_position: Mapped[int | None] = mapped_column(Integer)
    data_type: Mapped[str] = mapped_column(Text, nullable=False)
    is_nullable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    is_primary_key: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    business_name: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    synonyms: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    role: Mapped[str] = mapped_column(column_role, nullable=False, server_default="unknown")
    aggregation: Mapped[str | None] = mapped_column(Text)
    additivity: Mapped[str] = mapped_column(additivity_type, nullable=False, server_default="not_applicable")
    profile: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    status: Mapped[str] = mapped_column(approval_status, nullable=False, server_default="draft")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_by: Mapped[str] = mapped_column(Text, nullable=False, server_default="system")

    table: Mapped[TableMeta] = relationship(back_populates="columns")


class Relationship(Base):
    __tablename__ = "relationships"
    __table_args__ = (
        UniqueConstraint("from_column_id", "to_column_id"),
        CheckConstraint("from_column_id <> to_column_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=text("gen_random_uuid()"))
    from_column_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("columns_meta.id", ondelete="CASCADE"), nullable=False)
    to_column_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("columns_meta.id", ondelete="CASCADE"), nullable=False)
    cardinality: Mapped[str] = mapped_column(Text, nullable=False, server_default="many_to_one")
    source: Mapped[str] = mapped_column(rel_source, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(approval_status, nullable=False, server_default="draft")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_by: Mapped[str] = mapped_column(Text, nullable=False, server_default="system")


class Metric(Base):
    __tablename__ = "metrics"
    __table_args__ = (UniqueConstraint("source_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=text("gen_random_uuid()"))
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    business_name: Mapped[str | None] = mapped_column(Text)
    expression: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    owner: Mapped[str | None] = mapped_column(Text)
    synonyms: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    status: Mapped[str] = mapped_column(approval_status, nullable=False, server_default="draft")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_by: Mapped[str] = mapped_column(Text, nullable=False, server_default="system")


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=text("gen_random_uuid()"))
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False)
    stage: Mapped[str] = mapped_column(Text, nullable=False, server_default="pipeline")
    status: Mapped[str] = mapped_column(job_status, nullable=False, server_default="queued")
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    stats: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
