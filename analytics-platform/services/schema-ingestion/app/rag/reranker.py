from __future__ import annotations

import structlog

from app.config import get_settings
from app.rag.models import Chunk

log = structlog.get_logger(__name__)
_ranker = None


def _get_ranker():
    global _ranker
    if _ranker is None:
        from flashrank import Ranker
        _ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2")
    return _ranker


def rerank(question: str, chunks: list[Chunk]) -> list[Chunk]:
    settings = get_settings()
    if not chunks or settings.rerank_provider != "flashrank":
        return chunks[: settings.rag_rerank_top_n]
    try:
        from flashrank import RerankRequest

        passages = [{"id": chunk.id, "text": chunk.text[:2000]} for chunk in chunks]
        ranked = _get_ranker().rerank(RerankRequest(query=question, passages=passages))
        by_id = {chunk.id: chunk for chunk in chunks}
        ordered: list[Chunk] = []
        for item in ranked:
            chunk = by_id.get(str(item.get("id")))
            if chunk is None:
                continue
            chunk.score = float(item.get("score") or 0)
            ordered.append(chunk)
        if ordered and ordered[0].score < settings.rag_rerank_min_score:
            return []
        return ordered[: settings.rag_rerank_top_n]
    except Exception as exc:
        log.warning("rag_v2_rerank_skipped", error=type(exc).__name__)
        return chunks[: settings.rag_rerank_top_n]