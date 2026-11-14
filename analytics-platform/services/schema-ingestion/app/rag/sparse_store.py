from __future__ import annotations

import uuid

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.rag.models import Chunk, RetrievalScope

log = structlog.get_logger(__name__)


def _uuid_or_none(value: str | None):
    if not value:
        return None
    return uuid.UUID(str(value))


def replace_chunks(db: Session, chunks: list[Chunk], *, delete_document_id: str | None = None, delete_table_id: str | None = None) -> None:
    if delete_document_id:
        db.execute(text("DELETE FROM rag_chunks WHERE document_id = :id"), {"id": delete_document_id})
    if delete_table_id:
        db.execute(text("DELETE FROM rag_chunks WHERE table_id = :id"), {"id": delete_table_id})
    for chunk in chunks:
        db.execute(
            text(
                """
                INSERT INTO rag_chunks (
                    id, tenant_id, source_id, domain_id, parent_id, object_type,
                    document_id, table_id, section_path, file_name, body
                ) VALUES (
                    :id, :tenant_id, :source_id, :domain_id, :parent_id, :object_type,
                    :document_id, :table_id, :section_path, :file_name, :body
                )
                ON CONFLICT (id) DO UPDATE SET
                    body = EXCLUDED.body,
                    section_path = EXCLUDED.section_path,
                    file_name = EXCLUDED.file_name
                """
            ),
            {
                "id": chunk.id,
                "tenant_id": _uuid_or_none(chunk.tenant_id),
                "source_id": _uuid_or_none(chunk.source_id),
                "domain_id": _uuid_or_none(chunk.domain_id),
                "parent_id": chunk.parent_id,
                "object_type": chunk.object_type,
                "document_id": _uuid_or_none(chunk.document_id),
                "table_id": _uuid_or_none(chunk.table_id),
                "section_path": chunk.section_path,
                "file_name": chunk.file_name,
                "body": chunk.text,
            },
        )


def search(db: Session, query: str, scope: RetrievalScope, limit: int) -> list[Chunk]:
    if not query.strip():
        return []
    rows = db.execute(
        text(
            """
            SELECT id, tenant_id::text, source_id::text, domain_id::text, parent_id,
                   object_type, document_id::text, table_id::text, section_path, file_name, body,
                   ts_rank_cd(tsv, plainto_tsquery('english', :q)) AS rank
            FROM rag_chunks
            WHERE tenant_id = CAST(:tenant_id AS uuid)
              AND (:source_id IS NULL OR source_id = CAST(:source_id AS uuid))
              AND (:domain_id IS NULL OR domain_id = CAST(:domain_id AS uuid))
              AND tsv @@ plainto_tsquery('english', :q)
            ORDER BY rank DESC
            LIMIT :limit
            """
        ),
        {
            "q": query[:500],
            "tenant_id": scope.tenant_id,
            "source_id": scope.source_id,
            "domain_id": scope.domain_id,
            "limit": limit,
        },
    ).mappings().all()
    found: list[Chunk] = []
    allowed_types = set(scope.object_types or [])
    allowed_tables = set(scope.table_ids) if scope.table_ids is not None else None
    for row in rows:
        if allowed_types and row["object_type"] not in allowed_types:
            continue
        if allowed_tables is not None and row["table_id"] and row["table_id"] not in allowed_tables:
            continue
        found.append(
            Chunk(
                id=row["id"],
                text=row["body"],
                parent_id=row["parent_id"],
                object_type=row["object_type"],
                tenant_id=row["tenant_id"],
                source_id=row["source_id"],
                domain_id=row["domain_id"],
                document_id=row["document_id"],
                table_id=row["table_id"],
                section_path=row["section_path"] or "",
                file_name=row["file_name"] or "",
                score=float(row["rank"] or 0),
            )
        )
    return found