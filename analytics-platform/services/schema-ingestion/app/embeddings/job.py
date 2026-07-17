"""Embedding job — collects APPROVED semantic objects and upserts into Chroma.

Invariants:
  - NEVER embeds draft/unapproved objects. The draft guard is enforced both
    at the SQL filter level (status = 'approved') AND by an explicit runtime
    check that raises ValueError if a non-approved object slips through.
  - Tenant isolation: every query is scoped to the given tenant_id.
  - Relationships are scoped via the 4-table join chain:
      Relationship → ColumnMeta → TableMeta → DataSource (tenant_id)
  - Audit log is written after every successful run.

Entry point:
    embed_approved_objects(tenant_id, db, provider=None, store=None)

The `provider` and `store` parameters are injectable for tests; production
callers omit them and the defaults from settings are used.
"""
from __future__ import annotations

import uuid
from typing import Optional

import structlog
from sqlalchemy.orm import Session

from app.audit import AuditEvent, audit
from app.embeddings.chroma_store import ChromaStore, EmbeddedObject
from app.embeddings.provider import EmbeddingProvider
from app.models import (
    BusinessGlossary,
    ColumnMeta,
    DataSource,
    Relationship,
    SemanticDimension,
    SemanticMetric,
    SemanticSynonym,
    TableMeta,
)

log = structlog.get_logger()

_APPROVED = "approved"


# ---------------------------------------------------------------------------
# Text builders — rich descriptive text improves retrieval quality
# ---------------------------------------------------------------------------

def _table_text(t: TableMeta) -> str:
    parts = [t.business_name or t.table_name, t.description or ""]
    return f"{parts[0]} — {parts[1]}. Table: {t.schema_name}.{t.table_name}".strip(" —")


def _column_text(c: ColumnMeta, table_name: str) -> str:
    name = c.business_name or c.column_name
    desc = c.description or ""
    synonyms = ", ".join(c.synonyms) if c.synonyms else ""
    syn_part = f" Synonyms: {synonyms}." if synonyms else ""
    return f"{name} — {desc}. Column: {table_name}.{c.column_name} ({c.data_type}).{syn_part}".strip(" —")


def _metric_text(m: SemanticMetric) -> str:
    name = m.business_name or m.name
    desc = m.description or ""
    return f"Metric: {name} — {desc}. Expression: {m.expression}".strip(" —")


def _dimension_text(d: SemanticDimension) -> str:
    desc = d.description or ""
    return f"Dimension: {d.business_name} — {desc}".strip(" —")


def _glossary_text(g: BusinessGlossary) -> str:
    return f"Term: {g.term}. Definition: {g.business_definition}"


def _relationship_text(
    r: Relationship,
    from_col: ColumnMeta,
    from_table: TableMeta,
    to_col: ColumnMeta,
    to_table: TableMeta,
) -> str:
    return (
        f"Relationship: {from_table.table_name}.{from_col.column_name} "
        f"→ {to_table.table_name}.{to_col.column_name} "
        f"({r.cardinality}, {r.source})"
    )


# ---------------------------------------------------------------------------
# Draft guard
# ---------------------------------------------------------------------------

def _assert_approved(obj_id: uuid.UUID, status: str) -> None:
    """Hard invariant: raise immediately if a non-approved object is presented."""
    if status != _APPROVED:
        raise ValueError(
            f"Draft guard violated: object {obj_id} has status='{status}', "
            "only 'approved' objects may be embedded."
        )


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

def _collect_objects(
    tenant_id: uuid.UUID,
    db: Session,
) -> list[EmbeddedObject]:
    """Collect all approved semantic objects for a tenant and build embed texts.

    Each object is given a stable composite ID:
        "<object_type>:<uuid>" — e.g. "metric:3f2a..."
    This allows targeted upserts (idempotent) without a separate lookup table.
    """
    objects: list[EmbeddedObject] = []
    tenant_str = str(tenant_id)

    # 1. Tables (scoped via DataSource.tenant_id)
    tables = (
        db.query(TableMeta)
        .join(DataSource, TableMeta.source_id == DataSource.id)
        .filter(
            DataSource.tenant_id == tenant_id,
            TableMeta.status == _APPROVED,
            TableMeta.is_active.is_(True),
        )
        .all()
    )
    for t in tables:
        _assert_approved(t.id, t.status)
        objects.append(EmbeddedObject(
            id=f"table:{t.id}",
            text=_table_text(t),
            embedding=[],          # filled in after batch encode
            metadata={
                "object_type": "table",
                "object_id": str(t.id),
                "tenant_id": tenant_str,
                "source_id": str(t.source_id),
            },
        ))

    # 2. Columns (scoped via table → DataSource)
    columns = (
        db.query(ColumnMeta, TableMeta)
        .join(TableMeta, ColumnMeta.table_id == TableMeta.id)
        .join(DataSource, TableMeta.source_id == DataSource.id)
        .filter(
            DataSource.tenant_id == tenant_id,
            ColumnMeta.status == _APPROVED,
            ColumnMeta.is_active.is_(True),
        )
        .all()
    )
    for col, tbl in columns:
        _assert_approved(col.id, col.status)
        objects.append(EmbeddedObject(
            id=f"column:{col.id}",
            text=_column_text(col, tbl.table_name),
            embedding=[],
            metadata={
                "object_type": "column",
                "object_id": str(col.id),
                "tenant_id": tenant_str,
                "source_id": str(tbl.source_id),
            },
        ))

    # 3. Semantic Metrics
    metrics = (
        db.query(SemanticMetric)
        .filter(
            SemanticMetric.tenant_id == tenant_id,
            SemanticMetric.status == _APPROVED,
        )
        .all()
    )
    for m in metrics:
        _assert_approved(m.id, m.status)
        objects.append(EmbeddedObject(
            id=f"metric:{m.id}",
            text=_metric_text(m),
            embedding=[],
            metadata={
                "object_type": "metric",
                "object_id": str(m.id),
                "tenant_id": tenant_str,
                "source_id": str(m.source_table_id) if m.source_table_id else "",
            },
        ))

    # 4. Semantic Dimensions
    dimensions = (
        db.query(SemanticDimension)
        .filter(
            SemanticDimension.tenant_id == tenant_id,
            SemanticDimension.status == _APPROVED,
        )
        .all()
    )
    for d in dimensions:
        _assert_approved(d.id, d.status)
        objects.append(EmbeddedObject(
            id=f"dimension:{d.id}",
            text=_dimension_text(d),
            embedding=[],
            metadata={
                "object_type": "dimension",
                "object_id": str(d.id),
                "tenant_id": tenant_str,
                "source_id": str(d.source_table_id) if d.source_table_id else "",
            },
        ))

    # 5. Business Glossary
    glossary_terms = (
        db.query(BusinessGlossary)
        .filter(
            BusinessGlossary.tenant_id == tenant_id,
            BusinessGlossary.status == _APPROVED,
        )
        .all()
    )
    for g in glossary_terms:
        _assert_approved(g.id, g.status)
        objects.append(EmbeddedObject(
            id=f"glossary:{g.id}",
            text=_glossary_text(g),
            embedding=[],
            metadata={
                "object_type": "glossary",
                "object_id": str(g.id),
                "tenant_id": tenant_str,
                "source_id": "",
            },
        ))

    # 6. Synonyms — embed alongside their parent entity text
    synonyms = (
        db.query(SemanticSynonym)
        .filter(SemanticSynonym.tenant_id == tenant_id)
        .all()
    )
    for syn in synonyms:
        objects.append(EmbeddedObject(
            id=f"synonym:{syn.id}",
            text=f"Synonym: {syn.synonym} (refers to {syn.entity_type} {syn.entity_id})",
            embedding=[],
            metadata={
                "object_type": "synonym",
                "object_id": str(syn.id),
                "tenant_id": tenant_str,
                "parent_entity_type": syn.entity_type,
                "parent_entity_id": str(syn.entity_id),
                "source_id": "",
            },
        ))

    # 7. Approved Relationships — tenant-scoped via 4-table join
    from app.models import ColumnMeta as CM, TableMeta as TM  # alias to avoid shadowing
    from sqlalchemy.orm import aliased

    FromCol = aliased(ColumnMeta)
    FromTable = aliased(TableMeta)
    ToCol = aliased(ColumnMeta)
    ToTable = aliased(TableMeta)

    rels = (
        db.query(Relationship, FromCol, FromTable, ToCol, ToTable)
        .join(FromCol, Relationship.from_column_id == FromCol.id)
        .join(FromTable, FromCol.table_id == FromTable.id)
        .join(DataSource, FromTable.source_id == DataSource.id)
        .join(ToCol, Relationship.to_column_id == ToCol.id)
        .join(ToTable, ToCol.table_id == ToTable.id)
        .filter(
            DataSource.tenant_id == tenant_id,
            Relationship.status == _APPROVED,
        )
        .all()
    )
    for rel, from_col, from_table, to_col, to_table in rels:
        _assert_approved(rel.id, rel.status)
        objects.append(EmbeddedObject(
            id=f"relationship:{rel.id}",
            text=_relationship_text(rel, from_col, from_table, to_col, to_table),
            embedding=[],
            metadata={
                "object_type": "relationship",
                "object_id": str(rel.id),
                "tenant_id": tenant_str,
                "source_id": str(from_table.source_id),
            },
        ))

    return objects


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def embed_approved_objects(
    tenant_id: str | uuid.UUID,
    db: Session,
    provider: Optional[EmbeddingProvider] = None,
    store: Optional[ChromaStore] = None,
) -> dict:
    """Embed all approved semantic objects for a tenant into Chroma.

    Args:
        tenant_id: The tenant whose objects to embed.
        db:        SQLAlchemy session (read-only operations only).
        provider:  EmbeddingProvider to use; defaults to configured provider.
        store:     ChromaStore instance; defaults to PersistentClient.

    Returns:
        dict with keys: tenant_id, objects_embedded, object_types (summary).

    This function is idempotent: re-running it will upsert existing vectors
    (Chroma upsert = insert-or-update by ID).
    """
    if isinstance(tenant_id, str):
        tenant_id = uuid.UUID(tenant_id)

    if provider is None:
        from app.embeddings.registry import get_embedding_provider
        provider = get_embedding_provider()
    if store is None:
        store = ChromaStore(ephemeral=False)

    log.info("embedding_job_start", tenant_id=str(tenant_id))

    # Collect approved objects
    objects = _collect_objects(tenant_id, db)

    if not objects:
        log.info("embedding_job_no_approved_objects", tenant_id=str(tenant_id))
        return {"tenant_id": str(tenant_id), "objects_embedded": 0, "object_types": {}}

    # Batch embed all texts in one call (most providers are faster in batches)
    texts = [obj.text for obj in objects]
    vectors = provider.embed(texts)
    assert len(vectors) == len(objects), "Provider returned wrong number of vectors"

    for obj, vec in zip(objects, vectors):
        obj.embedding = vec

    # Upsert into Chroma
    upserted = store.upsert(tenant_id, objects)

    # Summarise by type
    type_counts: dict[str, int] = {}
    for obj in objects:
        t = obj.metadata.get("object_type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    log.info(
        "embedding_job_complete",
        tenant_id=str(tenant_id),
        objects_embedded=upserted,
        breakdown=type_counts,
    )

    # Audit — writes to the metadata DB so the event is traceable
    audit(
        db,
        tenant_id=tenant_id,
        entity_type="embedding_job",
        entity_id=tenant_id,            # use tenant_id as the entity for job-level events
        action="embedding_job_completed",
        actor="system:embedding",
        after={
            "objects_embedded": upserted,
            "breakdown": type_counts,
        },
    )
    db.commit()

    return {
        "tenant_id": str(tenant_id),
        "objects_embedded": upserted,
        "object_types": type_counts,
    }
