from __future__ import annotations

from app.rag.models import Chunk


def reciprocal_rank_fusion(lists: list[list[Chunk]], k: int = 60) -> list[Chunk]:
    scores: dict[str, float] = {}
    chosen: dict[str, Chunk] = {}
    for hits in lists:
        for rank, chunk in enumerate(hits, start=1):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (k + rank)
            chosen.setdefault(chunk.id, chunk)
    ordered = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)
    fused: list[Chunk] = []
    for chunk_id in ordered:
        chunk = chosen[chunk_id]
        chunk.score = scores[chunk_id]
        fused.append(chunk)
    return fused