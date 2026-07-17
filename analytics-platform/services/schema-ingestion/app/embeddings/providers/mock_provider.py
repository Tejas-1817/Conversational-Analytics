"""Deterministic mock embedding provider for unit tests and CI.

Returns fixed-dimension zero vectors by default, or simple keyword-based
vectors for retrieval tests (so top-k tests pass without a real model).
Never makes any network calls.
"""
import hashlib

from app.embeddings.provider import EmbeddingProvider

_DIM = 384  # matches all-MiniLM-L6-v2 so tests are dimensionally compatible


class MockEmbeddingProvider(EmbeddingProvider):
    """Returns deterministic vectors — safe for offline unit tests.

    The vector for each text is derived from a SHA-256 hash of the text,
    giving stable, non-zero values that are consistent across test runs.
    This is intentionally NOT semantic — use it only where you need a
    well-formed vector, not meaningful similarity.
    """

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        result = []
        for text in texts:
            digest = hashlib.sha256(text.encode()).digest()
            # Expand 32-byte digest to _DIM floats in [-1, 1]
            vec: list[float] = []
            while len(vec) < _DIM:
                for b in digest:
                    vec.append((b - 128) / 128.0)
                    if len(vec) == _DIM:
                        break
                if len(vec) < _DIM:
                    # Re-hash to extend
                    digest = hashlib.sha256(digest).digest()
            result.append(vec)
        return result

    @property
    def dimension(self) -> int:
        return _DIM
