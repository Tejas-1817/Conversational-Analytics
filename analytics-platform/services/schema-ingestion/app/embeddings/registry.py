"""EmbeddingProvider registry — same pattern as app/llm/registry.py."""
from typing import Dict, Type

from app.embeddings.provider import EmbeddingProvider


class EmbeddingRegistry:
    _providers: Dict[str, Type[EmbeddingProvider]] = {}
    _instances: Dict[str, EmbeddingProvider] = {}

    @classmethod
    def register(cls, name: str, provider_cls: Type[EmbeddingProvider]) -> None:
        cls._providers[name.lower()] = provider_cls

    @classmethod
    def get_provider(cls, name: str) -> EmbeddingProvider:
        key = name.lower()
        if key not in cls._providers:
            raise ValueError(
                f"Unknown embedding provider: '{name}'. "
                f"Available: {list(cls._providers)}"
            )
        if key not in cls._instances:
            cls._instances[key] = cls._providers[key]()
        return cls._instances[key]


# Register built-in providers.
# sentence_transformers import is deferred inside the class __init__, so
# importing this registry module is safe in a no-ML environment.
from app.embeddings.providers.mock_provider import MockEmbeddingProvider  # noqa: E402
from app.embeddings.providers.sentence_transformers_provider import SentenceTransformersProvider  # noqa: E402

EmbeddingRegistry.register("sentence_transformers", SentenceTransformersProvider)
EmbeddingRegistry.register("mock", MockEmbeddingProvider)


def get_embedding_provider() -> EmbeddingProvider:
    """Return the configured embedding provider from settings."""
    from app.config import get_settings  # local import avoids circular dependency
    return EmbeddingRegistry.get_provider(get_settings().embedding_provider)
