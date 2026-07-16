from typing import TypeVar, Any
from pydantic import BaseModel
from .base import ProviderInterface

T = TypeVar("T", bound=BaseModel)

class MockProvider(ProviderInterface):
    """Deterministic mock provider for CI testing."""
    def __init__(self, responses: dict[str, Any] = None):
        self.responses = responses or {"default": {}}

    def generate_chat_completion(self, prompt: str) -> str:
        return "Mock chat response"

    def generate_structured_json(self, prompt: str, schema: type[T]) -> str:
        # For simple mock, just return a JSON string based on the first response
        import json
        for key, value in self.responses.items():
            if key in prompt:
                return json.dumps(value)
        return json.dumps(list(self.responses.values())[0])

class NoOpProvider(ProviderInterface):
    """Silent provider for when AI is disabled."""
    def generate_chat_completion(self, prompt: str) -> str:
        raise RuntimeError("AI is explicitly disabled (llm_provider='none').")

    def generate_structured_json(self, prompt: str, schema: type[T]) -> str:
        raise RuntimeError("AI is explicitly disabled (llm_provider='none').")
