from __future__ import annotations

import structlog
from sqlalchemy.orm import Session, selectinload

from app.embeddings.chroma_store import ChromaStore, EmbeddedObject
from app.models import DataSource, TableMeta
from app.rag.chunkers.document_chunker import chunk_document
from app.rag.chunkers.schema_chunker import chunk_table
from app.rag.models import Chunk
from app.rag.sparse_store import replace_chunks

log = structlog.get_logger(__name__)
V2_SUFFIX = "v2"


def _embed_and_store(tenant_id: str, chunks: list[Chunk], source_id: str | None) -> None:
    if not chunks:
        return
    from app.embeddings.registry import get_embedding_provider

    vectors = get_embedding_provider().embed([chunk.text for chunk in chunks])
    objects = [
        EmbeddedObject(
            id=chunk.id,
            text=chunk.text,
            embedding=vector,
            metadata={
                "tenant_id": tenant_id,
                "source_id": source_id or "",
                "domain_id": chunk.domain_id or "",
                "document_id": chunk.document_id or "",
                "table_id": chunk.table_id or "",
                "object_type": chunk.object_type,
                "object_id": chunk.id,
                "parent_id": chunk.parent_id or "",
                "section_path": chunk.section_path,
                "file_name": chunk.file_name,
            },
        )
        for chunk, vector in zip(chunks, vectors)
    ]
    ChromaStore().upsert(
        tenant_id,
        objects,
        source_id=source_id,
        collection_suffix=V2_SUFFIX,
    )


def index_domain_document(
    db: Session,
    *,
    text: str,
    tenant_id: str,
    domain_id: str,
    document_id: str,
    file_name: str,
    source_id: str | None,
) -> int:
    chunks = chunk_document(
        text=text,
        tenant_id=str(tenant_id),
        domain_id=str(domain_id),
        document_id=str(document_id),
        file_name=file_name,
        source_id=str(source_id) if source_id else None,
    )
    replace_chunks(db, chunks, delete_document_id=str(document_id))
    db.commit()
    _embed_and_store(str(tenant_id), chunks, str(source_id) if source_id else None)
    return len(chunks)


def index_schema_tables(db: Session, tenant_id) -> int:
    tables = (
        db.query(TableMeta)
        .options(selectinload(TableMeta.columns))
        .join(DataSource, TableMeta.source_id == DataSource.id)
        .filter(DataSource.tenant_id == tenant_id, TableMeta.is_active.is_(True))
        .all()
    )
    count = 0
    for table in tables:
        chunks = chunk_table(table, str(tenant_id))
        replace_chunks(db, chunks, delete_table_id=str(table.id))
        _embed_and_store(str(tenant_id), chunks, str(table.source_id))
        count += len(chunks)
    db.commit()
    log.info("rag_v2_schema_indexed", tenant_id=str(tenant_id), chunks=count)
    return count