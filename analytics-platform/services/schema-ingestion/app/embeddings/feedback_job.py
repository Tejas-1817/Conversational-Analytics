"""Feedback embedding job — collects ApprovedSQLExample objects and upserts into Chroma.

Invariants:
  - Tenant isolation: every query is scoped to the given tenant_id.
  - Audit log is written after every successful run.
"""
from __future__ import annotations

import uuid
from typing import Optional

import structlog
from sqlalchemy.orm import Session

from app.audit import AuditEvent, audit
from app.embeddings.chroma_store import ChromaStore, EmbeddedObject
from app.embeddings.provider import EmbeddingProvider
from app.models import ApprovedSQLExample

log = structlog.get_logger()

def _example_text(ex: ApprovedSQLExample) -> str:
    return f"Approved Example: {ex.question}\nSQL: {ex.generated_sql}"

def _collect_examples(tenant_id: uuid.UUID, db: Session) -> list[EmbeddedObject]:
    objects: list[EmbeddedObject] = []
    tenant_str = str(tenant_id)

    examples = (
        db.query(ApprovedSQLExample)
        .filter(ApprovedSQLExample.tenant_id == tenant_id)
        .all()
    )
    for ex in examples:
        objects.append(EmbeddedObject(
            id=f"approved_example:{ex.id}",
            text=_example_text(ex),
            embedding=[],
            metadata={
                "object_type": "approved_example",
                "object_id": str(ex.id),
                "tenant_id": tenant_str,
                "source_id": "",
            },
        ))

    return objects

def embed_approved_examples(
    tenant_id: str | uuid.UUID,
    db: Session,
    provider: Optional[EmbeddingProvider] = None,
    store: Optional[ChromaStore] = None,
) -> dict:
    if isinstance(tenant_id, str):
        tenant_id = uuid.UUID(tenant_id)

    if provider is None:
        from app.embeddings.registry import get_embedding_provider
        provider = get_embedding_provider()
    if store is None:
        store = ChromaStore(ephemeral=False)

    log.info("feedback_embedding_job_start", tenant_id=str(tenant_id))

    objects = _collect_examples(tenant_id, db)

    if not objects:
        log.info("feedback_embedding_job_no_objects", tenant_id=str(tenant_id))
        return {"tenant_id": str(tenant_id), "objects_embedded": 0, "object_types": {}}

    texts = [obj.text for obj in objects]
    vectors = provider.embed(texts)
    assert len(vectors) == len(objects), "Provider returned wrong number of vectors"

    for obj, vec in zip(objects, vectors):
        obj.embedding = vec

    upserted = store.upsert(tenant_id, objects)

    log.info(
        "feedback_embedding_job_complete",
        tenant_id=str(tenant_id),
        objects_embedded=upserted,
    )

    audit(
        db,
        tenant_id=tenant_id,
        entity_type="feedback_embedding_job",
        entity_id=tenant_id,
        action="feedback_embedding_job_completed",
        actor="system:embedding",
        after={"objects_embedded": upserted},
    )
    db.commit()

    return {
        "tenant_id": str(tenant_id),
        "objects_embedded": upserted,
        "object_types": {"approved_example": upserted},
    }
