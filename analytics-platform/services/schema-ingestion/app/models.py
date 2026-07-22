"""SQLAlchemy ORM models. DDL migrations are the source of truth.
Phase 6 adds: Tenant, OIDCProvider, ApiKey, RLSPolicy, ColumnSecurityPolicy, TenantPolicy."""
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    Text,
    UniqueConstraint,
    text,
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
user_role = ENUM("ADMIN", "ANALYST", "VIEWER",
                 name="user_role", create_type=False)
agg_type = ENUM("SUM", "AVG", "COUNT", "COUNT_DISTINCT", "MIN", "MAX", "CUSTOM",
                name="agg_type", create_type=False)
join_type = ENUM("INNER", "LEFT", "RIGHT", "FULL",
                 name="join_type", create_type=False)
entity_type_enum = ENUM("METRIC", "DIMENSION", "GLOSSARY",
                        name="entity_type", create_type=False)
time_grain = ENUM("YEAR", "QUARTER", "MONTH", "WEEK", "DAY", "HOUR", "NONE",
                  name="time_grain", create_type=False)
col_security_action = ENUM("deny", "mask", "hash", "partial_mask",
                           name="col_security_action", create_type=False)
generation_status_enum = ENUM("GENERATING", "ACTIVE", "REVIEW_REQUIRED", "REJECTED",
                              name="generation_status", create_type=False)
generation_source_enum = ENUM("MANUAL", "AI",
                              name="generation_source", create_type=False)


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
    metadata_versions: Mapped[list["MetadataVersion"]] = relationship(back_populates="source", cascade="all, delete-orphan")


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
    indexes: Mapped[list["IndexMeta"]] = relationship(back_populates="table", cascade="all, delete-orphan")


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


class MetadataVersion(Base):
    __tablename__ = "metadata_versions"
    __table_args__ = (UniqueConstraint("source_id", "version_number"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    sync_status: Mapped[str] = mapped_column(job_status, nullable=False, server_default="queued")
    sync_duration: Mapped[float | None] = mapped_column(Numeric)

    source: Mapped[DataSource] = relationship(back_populates="metadata_versions")


class IndexMeta(Base):
    __tablename__ = "index_meta"
    __table_args__ = (UniqueConstraint("table_id", "index_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    table_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tables_meta.id", ondelete="CASCADE"), nullable=False)
    index_name: Mapped[str] = mapped_column(Text, nullable=False)
    column_names: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    is_unique: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    table: Mapped[TableMeta] = relationship(back_populates="indexes")


class SemanticDimension(Base):
    __tablename__ = "semantic_dimensions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    business_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    semantic_model_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("semantic_models.id", ondelete="CASCADE"))
    source_table_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tables_meta.id", ondelete="CASCADE"))
    source_column_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("columns_meta.id", ondelete="CASCADE"))
    data_type: Mapped[str] = mapped_column(Text, nullable=False)
    is_time_dimension: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    time_granularity: Mapped[str] = mapped_column(time_grain, nullable=False, server_default="NONE")
    visibility: Mapped[str] = mapped_column(Text, nullable=False, server_default="visible")
    status: Mapped[str] = mapped_column(approval_status, nullable=False, server_default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    generation_source: Mapped[str] = mapped_column(generation_source_enum, nullable=False, server_default="MANUAL")
    confidence_score: Mapped[float | None] = mapped_column(Numeric(4, 3))
    prompt_version: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(generation_status_enum, nullable=False, server_default="ACTIVE")


class SemanticJoin(Base):
    __tablename__ = "semantic_joins"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    semantic_model_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("semantic_models.id", ondelete="CASCADE"))
    left_table_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tables_meta.id", ondelete="CASCADE"))
    left_column_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("columns_meta.id", ondelete="CASCADE"))
    right_table_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tables_meta.id", ondelete="CASCADE"))
    right_column_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("columns_meta.id", ondelete="CASCADE"))
    join_condition: Mapped[str] = mapped_column(Text, nullable=False)
    join_type: Mapped[str] = mapped_column(join_type, nullable=False, server_default="LEFT")
    cardinality: Mapped[str] = mapped_column(Text, nullable=False, server_default="many_to_one")
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, server_default="1.0")
    status: Mapped[str] = mapped_column(approval_status, nullable=False, server_default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    generation_source: Mapped[str] = mapped_column(generation_source_enum, nullable=False, server_default="MANUAL")
    prompt_version: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(generation_status_enum, nullable=False, server_default="ACTIVE")


class MetricAllowedDimension(Base):
    __tablename__ = "metric_allowed_dimensions"
    metric_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("semantic_metrics.id", ondelete="CASCADE"), primary_key=True)
    dimension_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("semantic_dimensions.id", ondelete="CASCADE"), primary_key=True)


class MetricAllowedFilter(Base):
    __tablename__ = "metric_allowed_filters"
    metric_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("semantic_metrics.id", ondelete="CASCADE"), primary_key=True)
    filter_dimension_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("semantic_dimensions.id", ondelete="CASCADE"), primary_key=True)


class SemanticMetric(Base):
    __tablename__ = "semantic_metrics"
    __table_args__ = (UniqueConstraint("semantic_model_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    business_name: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    semantic_model_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("semantic_models.id", ondelete="CASCADE"))
    is_calculated: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    aggregation_type: Mapped[str] = mapped_column(agg_type, nullable=False, server_default="SUM")
    expression: Mapped[str] = mapped_column(Text, nullable=False)
    source_table_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tables_meta.id", ondelete="SET NULL"))
    source_column_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("columns_meta.id", ondelete="SET NULL"))
    owner: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(approval_status, nullable=False, server_default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    generation_source: Mapped[str] = mapped_column(generation_source_enum, nullable=False, server_default="MANUAL")
    confidence_score: Mapped[float | None] = mapped_column(Numeric(4, 3))
    prompt_version: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(generation_status_enum, nullable=False, server_default="ACTIVE")


class BusinessGlossary(Base):
    __tablename__ = "business_glossary"
    __table_args__ = (UniqueConstraint("semantic_model_id", "term"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    semantic_model_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("semantic_models.id", ondelete="CASCADE"))
    term: Mapped[str] = mapped_column(Text, nullable=False)
    business_definition: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(approval_status, nullable=False, server_default="draft")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)
    generation_source: Mapped[str] = mapped_column(generation_source_enum, nullable=False, server_default="MANUAL")
    confidence_score: Mapped[float | None] = mapped_column(Numeric(4, 3))
    prompt_version: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(generation_status_enum, nullable=False, server_default="ACTIVE")


class GlossaryLink(Base):
    __tablename__ = "glossary_links"
    glossary_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("business_glossary.id", ondelete="CASCADE"), primary_key=True)
    entity_type: Mapped[str] = mapped_column(entity_type_enum, primary_key=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)


class SemanticSynonym(Base):
    __tablename__ = "semantic_synonyms"
    __table_args__ = (UniqueConstraint("tenant_id", "entity_type", "entity_id", "synonym"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_type: Mapped[str] = mapped_column(entity_type_enum, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    synonym: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))


class MetricVersion(Base):
    __tablename__ = "metric_versions"
    __table_args__ = (UniqueConstraint("metric_id", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    metric_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("semantic_metrics.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    change_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)


class DimensionVersion(Base):
    __tablename__ = "dimension_versions"
    __table_args__ = (UniqueConstraint("dimension_id", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    dimension_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("semantic_dimensions.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    change_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)


class JoinVersion(Base):
    __tablename__ = "join_versions"
    __table_args__ = (UniqueConstraint("join_id", "version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    join_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("semantic_joins.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    change_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)


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
    # Phase 6 security fields
    ip_address: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(Text)
    event_type: Mapped[str | None] = mapped_column(Text)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("tenant_id", "email"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                          server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(user_role, nullable=False, server_default="VIEWER")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    token_id: Mapped[str] = mapped_column(Text, primary_key=True)
    revoked_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("tenant_id", "id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    messages: Mapped[list["ConversationMessage"]] = relationship(back_populates="conversation", cascade="all, delete-orphan", order_by="ConversationMessage.created_at")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False) # 'user' or 'assistant'
    content: Mapped[str] = mapped_column(Text, nullable=False) # raw text
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="processing") # processing, complete, error

    # Metadata for observability and UI rendering
    route: Mapped[str | None] = mapped_column(Text)
    trace: Mapped[dict | None] = mapped_column(JSONB)
    intent: Mapped[dict | None] = mapped_column(JSONB)
    semantic_context: Mapped[dict | None] = mapped_column(JSONB)
    query_plan: Mapped[dict | None] = mapped_column(JSONB)
    generated_sql: Mapped[str | None] = mapped_column(Text)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer)
    result_data: Mapped[dict | None] = mapped_column(JSONB)
    chart_recommendation: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(4, 3))
    confidence_reason: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class SavedInsight(Base):
    __tablename__ = "saved_insights"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Store the query intent or exactly what was asked so it can be re-run
    query: Mapped[str] = mapped_column(Text, nullable=False)

    # Optionally store the last known result snapshot or chart config
    chart_config: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))


class Dashboard(Base):
    __tablename__ = "dashboards"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    widgets: Mapped[list["DashboardWidget"]] = relationship(back_populates="dashboard", cascade="all, delete-orphan")


class DashboardWidget(Base):
    __tablename__ = "dashboard_widgets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    dashboard_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False)
    insight_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("saved_insights.id", ondelete="CASCADE"), nullable=False)

    # Layout positions for grid
    x: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    y: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    w: Mapped[int] = mapped_column(Integer, nullable=False, server_default="4")
    h: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")

    dashboard: Mapped[Dashboard] = relationship(back_populates="widgets")
    insight: Mapped[SavedInsight] = relationship()


# =============================================================================
# Phase 6 — Enterprise Multi-Tenancy & Production Security Models
# =============================================================================


class Tenant(Base):
    """First-class Organization / Tenant entity."""
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(Text)
    plan: Mapped[str] = mapped_column(Text, nullable=False, server_default="starter")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    max_users: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    max_sources: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False, server_default="system")


class TenantPolicy(Base):
    """Per-tenant rate limits and governance settings."""
    __tablename__ = "tenant_policies"

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    rate_chat_per_min: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100")
    rate_login_per_min: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    rate_export_per_min: Mapped[int] = mapped_column(Integer, nullable=False, server_default="20")
    max_query_rows: Mapped[int] = mapped_column(Integer, nullable=False, server_default="50000")
    query_timeout_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="30000")
    allow_raw_sql: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    require_mfa: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    session_timeout_min: Mapped[int] = mapped_column(Integer, nullable=False, server_default="480")
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))


class OIDCProvider(Base):
    """Pluggable SSO / OIDC configuration per tenant."""
    __tablename__ = "oidc_providers"
    __table_args__ = (UniqueConstraint("tenant_id", "provider_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    provider_name: Mapped[str] = mapped_column(Text, nullable=False)
    client_id: Mapped[str] = mapped_column(Text, nullable=False)
    client_secret_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    issuer_url: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{openid,email,profile}'"))
    claim_mapping: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))


class ApiKey(Base):
    """Service account / machine API keys."""
    __tablename__ = "api_keys"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    key_prefix: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    last_used_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))


class RLSPolicy(Base):
    """Row-Level Security — injects WHERE clauses based on user claims."""
    __tablename__ = "rls_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"))
    table_name: Mapped[str | None] = mapped_column(Text)
    filter_column: Mapped[str] = mapped_column(Text, nullable=False)
    filter_operator: Mapped[str] = mapped_column(Text, nullable=False, server_default="=")
    filter_claim: Mapped[str] = mapped_column(Text, nullable=False)
    applies_to_roles: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{ANALYST,VIEWER}'"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)


class ColumnSecurityPolicy(Base):
    """Column-Level Security — masking, denial, and hashing of sensitive fields."""
    __tablename__ = "column_security_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"))
    table_name: Mapped[str] = mapped_column(Text, nullable=False)
    column_name: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(col_security_action, nullable=False)
    mask_char: Mapped[str | None] = mapped_column(Text, server_default="*")
    visible_chars: Mapped[int | None] = mapped_column(Integer, server_default="4")
    applies_to_roles: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{VIEWER}'"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)


# =============================================================================
# Phase 7 — AI Evaluation, Reliability & Benchmarking Models
# =============================================================================

class BenchmarkCollection(Base):
    __tablename__ = "benchmark_collections"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    created_by: Mapped[str] = mapped_column(Text, nullable=False)

    datasets: Mapped[list["EvaluationDataset"]] = relationship(back_populates="collection", cascade="all, delete-orphan")


class EvaluationDataset(Base):
    __tablename__ = "evaluation_datasets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    collection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("benchmark_collections.id", ondelete="CASCADE"), nullable=False)

    # Inputs
    question: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))

    # Expected Outputs (JSONB to accommodate structured expectations)
    expected_intent: Mapped[dict | None] = mapped_column(JSONB)
    expected_plan: Mapped[dict | None] = mapped_column(JSONB)
    expected_sql: Mapped[str | None] = mapped_column(Text)
    expected_result: Mapped[dict | None] = mapped_column(JSONB)
    expected_chart: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    collection: Mapped[BenchmarkCollection] = relationship(back_populates="datasets")


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    collection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("benchmark_collections.id", ondelete="CASCADE"), nullable=False)

    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="running")
    overall_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    pass_rate: Mapped[float | None] = mapped_column(Numeric(5, 4))
    avg_latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_rate: Mapped[float | None] = mapped_column(Numeric(5, 4))

    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    finished_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    triggered_by: Mapped[str] = mapped_column(Text, nullable=False)

    results: Mapped[list["EvaluationResult"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    collection: Mapped[BenchmarkCollection] = relationship()


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False)

    # Generated Outputs
    generated_intent: Mapped[dict | None] = mapped_column(JSONB)
    generated_plan: Mapped[dict | None] = mapped_column(JSONB)
    generated_sql: Mapped[str | None] = mapped_column(Text)
    generated_result: Mapped[dict | None] = mapped_column(JSONB)
    generated_chart: Mapped[str | None] = mapped_column(Text)
    generated_answer: Mapped[str | None] = mapped_column(Text)

    execution_time_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)

    # Component Scores (0.0 to 1.0)
    intent_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    plan_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    sql_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    result_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    chart_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    nl_score: Mapped[float | None] = mapped_column(Numeric(5, 4))

    # Final Reliability Score
    reliability_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    is_pass: Mapped[bool | None] = mapped_column(Boolean)
    failure_reasons: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))

    run: Mapped[EvaluationRun] = relationship(back_populates="results")
    dataset: Mapped[EvaluationDataset] = relationship()


class SemanticModel(Base):
    __tablename__ = "semantic_models"
    __table_args__ = (UniqueConstraint("source_id", "semantic_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False)
    metadata_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("metadata_versions.id", ondelete="CASCADE"), nullable=False)
    semantic_version: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    generated_by_model: Mapped[str] = mapped_column(Text, nullable=False)
    generation_status: Mapped[str] = mapped_column(generation_status_enum, nullable=False, server_default="ACTIVE")
    confidence_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    
    # Phase 3 Tracking Fields
    generation_source: Mapped[str | None] = mapped_column(generation_source_enum)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    prompt_version: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str | None] = mapped_column(Text)


class BusinessOntology(Base):
    __tablename__ = "business_ontology"
    __table_args__ = (UniqueConstraint("semantic_model_id", "domain"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    semantic_model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("semantic_models.id", ondelete="CASCADE"), nullable=False)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, server_default="1.0")
    status: Mapped[str] = mapped_column(generation_status_enum, nullable=False, server_default="ACTIVE")
    generated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="ai_generated")
    
    # Phase 3 Tracking Fields
    generation_source: Mapped[str | None] = mapped_column(generation_source_enum)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    prompt_version: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str | None] = mapped_column(Text)


class SemanticKPI(Base):
    __tablename__ = "semantic_kpis"
    __table_args__ = (UniqueConstraint("semantic_model_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    semantic_model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("semantic_models.id", ondelete="CASCADE"), nullable=False)
    ontology_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("business_ontology.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    formula: Mapped[str] = mapped_column(Text, nullable=False)
    dimensions: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    measures: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, server_default="1.0")
    status: Mapped[str] = mapped_column(generation_status_enum, nullable=False, server_default="ACTIVE")
    generated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="ai_generated")
    
    # Phase 3 Tracking Fields
    generation_source: Mapped[str | None] = mapped_column(generation_source_enum)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    prompt_version: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str | None] = mapped_column(Text)


class DashboardRecommendation(Base):
    __tablename__ = "dashboard_recommendations"
    __table_args__ = (UniqueConstraint("semantic_model_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    semantic_model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("semantic_models.id", ondelete="CASCADE"), nullable=False)
    ontology_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("business_ontology.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    business_goal: Mapped[str | None] = mapped_column(Text)
    structure: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, server_default="1.0")
    status: Mapped[str] = mapped_column(generation_status_enum, nullable=False, server_default="ACTIVE")
    generated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="ai_generated")
    
    # Phase 3 Tracking Fields
    generation_source: Mapped[str | None] = mapped_column(generation_source_enum)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    prompt_version: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str | None] = mapped_column(Text)


class ChartRecommendation(Base):
    __tablename__ = "chart_recommendations"
    __table_args__ = (UniqueConstraint("dashboard_id", "kpi_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    semantic_model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("semantic_models.id", ondelete="CASCADE"), nullable=False)
    dashboard_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dashboard_recommendations.id", ondelete="CASCADE"), nullable=False)
    kpi_name: Mapped[str] = mapped_column(Text, nullable=False)
    insight_type: Mapped[str] = mapped_column(Text, nullable=False)
    chart_type: Mapped[str] = mapped_column(Text, nullable=False)
    applicability: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, server_default="1.0")
    status: Mapped[str] = mapped_column(generation_status_enum, nullable=False, server_default="ACTIVE")
    generated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="ai_generated")


class SuggestedQuestion(Base):
    __tablename__ = "suggested_questions"
    __table_args__ = (UniqueConstraint("semantic_model_id", "question"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    semantic_model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("semantic_models.id", ondelete="CASCADE"), nullable=False)
    ontology_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("business_ontology.id", ondelete="SET NULL"))
    entity_name: Mapped[str] = mapped_column(Text, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    filter_logic: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, server_default="1.0")
    status: Mapped[str] = mapped_column(generation_status_enum, nullable=False, server_default="ACTIVE")
    generated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="ai_generated")
    
    # Phase 3 Tracking Fields
    generation_source: Mapped[str | None] = mapped_column(generation_source_enum)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    prompt_version: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str | None] = mapped_column(Text)


class AIContext(Base):
    __tablename__ = "ai_context"
    __table_args__ = (UniqueConstraint("semantic_model_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    semantic_model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("semantic_models.id", ondelete="CASCADE"), nullable=False)
    purpose: Mapped[str | None] = mapped_column(Text)
    default_filters: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    time_intelligence: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    chart_preferences: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    context_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, server_default="1.0")
    status: Mapped[str] = mapped_column(generation_status_enum, nullable=False, server_default="ACTIVE")
    generated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="ai_generated")
    
    # Phase 3 Tracking Fields
    generation_source: Mapped[str | None] = mapped_column(generation_source_enum)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    prompt_version: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str | None] = mapped_column(Text)


class UserFeedback(Base):
    __tablename__ = "user_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversation_messages.id", ondelete="CASCADE"), nullable=False)
    is_positive: Mapped[bool] = mapped_column(Boolean, nullable=False)
    correction: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))


class ApprovedSQLExample(Base):
    __tablename__ = "approved_sql_examples"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    generated_sql: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=text("now()"))
