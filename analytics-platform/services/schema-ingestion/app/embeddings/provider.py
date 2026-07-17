"""Abstract EmbeddingProvider interface.

Mirrors the pattern in app/llm/providers/base.py: providers ONLY handle
the embedding model IO. No caching, retrying, or logging here.
"""
import abc


class EmbeddingProvider(abc.ABC):
    """Swappable embedding model interface.

    All implementations must be fully local / offline — no cloud API calls.
    The contract: given a list of texts, return a list of float vectors of
    uniform dimensionality.
    """

    @abc.abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts.

        Args:
            texts: Non-empty list of strings to embed.

        Returns:
            List of float vectors, one per input text, all same length.
        """

    @property
    @abc.abstractmethod
    def dimension(self) -> int:
        """Dimensionality of the embedding vectors produced by this provider."""
