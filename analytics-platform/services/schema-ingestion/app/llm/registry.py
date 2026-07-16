from typing import Dict, Type

from .providers.base import ProviderInterface
from .providers.gemini import GeminiProvider
from .providers.huggingface import HuggingFaceProvider
from .providers.mock import MockProvider, NoOpProvider

class ProviderRegistry:
    _providers: Dict[str, Type[ProviderInterface]] = {}

    @classmethod
    def register(cls, name: str, provider_cls: Type[ProviderInterface]):
        cls._providers[name.lower()] = provider_cls

    @classmethod
    def get_provider(cls, name: str) -> ProviderInterface:
        name = name.lower()
        if name not in cls._providers:
            raise ValueError(f"Unknown LLM provider: {name}")
        
        # Instantiate provider
        return cls._providers[name]()

# Register standard providers
ProviderRegistry.register("gemini", GeminiProvider)
ProviderRegistry.register("huggingface", HuggingFaceProvider)
ProviderRegistry.register("mock", MockProvider)
ProviderRegistry.register("none", NoOpProvider)

def get_llm_provider_from_config() -> ProviderInterface:
    from app.config import get_settings
    settings = get_settings()
    return ProviderRegistry.get_provider(settings.llm_provider)
