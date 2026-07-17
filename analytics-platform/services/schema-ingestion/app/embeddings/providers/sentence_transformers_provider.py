"""Local on-device embedding provider using sentence-transformers.

The model runs entirely on the local machine — no network calls after the
initial one-time download to the HuggingFace cache directory
(~/.cache/huggingface/hub/).  Set TRANSFORMERS_OFFLINE=1 to enforce that
mode explicitly.

Chosen model default: all-MiniLM-L6-v2
  - 22 M params, 384-dim output
  - Well-supported, MIT-licensed, fast on CPU
  - Excellent semantic similarity quality for short texts
"""
import os

from app.config import get_settings
from app.embeddings.provider import EmbeddingProvider


class SentenceTransformersProvider(EmbeddingProvider):
    """On-device embedding via sentence-transformers (no cloud API)."""

    def __init__(self, model_name: str | None = None) -> None:
        # Import here so the heavy library is only loaded when this provider
        # is actually instantiated (not at module import time, which keeps
        # tests fast when using MockEmbeddingProvider).
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HUB_OFFLINE"] = "1"
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        name = model_name or get_settings().embedding_model
        self._model = SentenceTransformer(name)
        self._dimension = self._model.get_sentence_embedding_dimension()

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts using the local sentence-transformers model.

        Returns a list of Python float lists (not numpy arrays) so the output
        is JSON-serialisable and compatible with Chroma's expected input format.
        """
        if not texts:
            return []
        vectors = self._model.encode(texts, convert_to_numpy=True)
        return [v.tolist() for v in vectors]

    @property
    def dimension(self) -> int:
        return self._dimension
