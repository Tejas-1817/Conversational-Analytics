import abc
from typing import TypeVar

from pydantic import BaseModel

from app.llm.schema_adapter import ProviderCapabilities, StructuredOutputRequest

T = TypeVar("T", bound=BaseModel)

class ProviderInterface(abc.ABC):
    """
    Abstract base class for all LLM providers.
    Following Phase 1 principles, Providers ONLY handle network IO to the LLM.
    They DO NOT handle caching, retrying, validation, or logging.
    """

    capabilities = ProviderCapabilities()
    model_name = "unknown"

    @abc.abstractmethod
    def generate_chat_completion(self, prompt: str) -> str:
        """
        Generate a plain text chat completion.
        """
        pass

    @abc.abstractmethod
    def generate_structured_json(
        self,
        prompt: str,
        schema: type[T],
        request: StructuredOutputRequest | None = None,
    ) -> str:
        """
        Generate a structured JSON string adhering to the provided Pydantic schema.
        Note: The provider only returns the raw string. The Orchestrator handles validation.
        """
        pass
