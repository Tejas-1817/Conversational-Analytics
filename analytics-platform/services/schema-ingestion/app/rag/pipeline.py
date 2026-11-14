from __future__ import annotations

import structlog
from sqlalchemy.orm import Session

from app.config import get_settings
from app.embeddings.chroma_store import ChromaStore
from app.embeddings.registry import get_embedding_provider
from app.rag.hybrid import reciprocal_rank_fusion
from app.rag.models import Chunk, RetrievalScope
from app.rag.query_rewriter import rewrite
from app.rag.reranker import rerank
from app.rag.sparse_store import search as sparse_search

log = structlog.get_logger(__name__)
V2_SUFFIX = "v2"


def _allow(chunk: Chunk, scope: RetrievalScope) -> bool:
    if chunk.tenant_id and chunk.tenant_id != str(scope.tenant_id):
        return False
    if scope.domain_id and chunk.domain_id and chunk.domain_id != str(scope.domain_id):
        return False
    if scope.object_types and chunk.object_type not in scope.object_types:
        return False
    if scope.table_ids is not None and chunk.table_id and chunk.table_id not in set(scope.table_ids):
        return False
    return True


def _dense(query: str, scope: RetrievalScope, limit: int) -> list[Chunk]:
    vector = get_embedding_provider().embed([query])[0]
    hits = ChromaStore().query(
        tenant_id=scope.tenant_id,
        query_embedding=vector,
        n_results=limit,
        source_id=scope.source_id,
        object_types=scope.object_types,
        collection_suffix=V2_SUFFIX,
    )
    found: list[Chunk] = []
    for hit in hits:
        meta = hit.metadata or {}
        chunk = Chunk(
            id=hit.id,
            text=hit.text,
            parent_id=meta.get("parent_id") or None,
            object_type=str(meta.get("object_type") or ""),
            tenant_id=str(meta.get("tenant_id") or scope.tenant_id),
            source_id=meta.get("source_id") or None,
            domain_id=meta.get("domain_id") or None,
            document_id=meta.get("document_id") or None,
            table_id=meta.get("table_id") or None,
            section_path=str(meta.get("section_path") or ""),
            file_name=str(meta.get("file_name") or ""),
            distance=hit.distance,
            metadata=meta,
        )
        if _allow(chunk, scope):
            found.append(chunk)
    return found


def retrieve(
    *,
    question: str,
    scope: RetrievalScope,
    db: Session | None = None,
    conversation_context: str = "",
) -> list[Chunk]:
    if not scope.tenant_id:
        raise ValueError("tenant_id is required")
    settings = get_settings()
    queries = rewrite(question, conversation_context)
    dense_lists: list[list[Chunk]] = []
    sparse_lists: list[list[Chunk]] = []
    for item in queries:
        dense_lists.append(_dense(item, scope, settings.rag_dense_k))
        if settings.rag_hybrid_enabled and db is not None:
            try:
                sparse_lists.append(sparse_search(db, item, scope, settings.rag_dense_k))
            except Exception as exc:
                log.warning("rag_v2_sparse_failed", error=type(exc).__name__)
    fused = reciprocal_rank_fusion([*dense_lists, *sparse_lists], k=settings.rag_rrf_k)
    fused = [chunk for chunk in fused if _allow(chunk, scope)]
    return rerank(question, fused[: settings.rag_dense_k])