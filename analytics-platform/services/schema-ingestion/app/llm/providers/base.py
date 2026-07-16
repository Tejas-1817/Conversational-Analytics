import abc
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

class ProviderInterface(abc.ABC):
    """
    Abstract base class for all LLM providers.
    Following Phase 1 principles, Providers ONLY handle network IO to the LLM.
    They DO NOT handle caching, retrying, validation, or logging.
    """

    @abc.abstractmethod
    def generate_chat_completion(self, prompt: str) -> str:
        """
        Generate a plain text chat completion.
        """
        pass

    @abc.abstractmethod
    def generate_structured_json(self, prompt: str, schema: type[T]) -> str:
        """
        Generate a structured JSON string adhering to the provided Pydantic schema.
        Note: The provider only returns the raw string. The Orchestrator handles validation.
        """
        pass
