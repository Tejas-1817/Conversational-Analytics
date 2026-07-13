import abc
from typing import Type, TypeVar, Any
from pydantic import BaseModel
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential
from app.config import get_settings

T = TypeVar("T", bound=BaseModel)

class LLMProvider(abc.ABC):
    @abc.abstractmethod
    def generate_structured(self, prompt: str, schema: Type[T]) -> T:
        pass


class GeminiProvider(LLMProvider):
    def __init__(self):
        settings = get_settings()
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model_name = "gemini-2.5-pro" # Can be made configurable
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def generate_structured(self, prompt: str, schema: Type[T]) -> T:
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        # Parse output using pydantic
        return schema.model_validate_json(response.text)


class MockProvider(LLMProvider):
    """Deterministic mock provider for CI testing."""
    def __init__(self, responses: dict[str, Any]):
        self.responses = responses
        
    def generate_structured(self, prompt: str, schema: Type[T]) -> T:
        # For simplicity, return a preconfigured response based on some simple keyword matching or just a single mock response
        # In a real setup, we might match on regex or prompt substrings
        for key, value in self.responses.items():
            if key in prompt:
                return schema.model_validate(value)
        # Fallback to the first available if not matched
        return schema.model_validate(list(self.responses.values())[0])


class NoOpProvider(LLMProvider):
    """Silent provider for when AI is disabled."""
    def generate_structured(self, prompt: str, schema: Type[T]) -> T:
        # Return an empty/default instance of the schema
        # (This might fail if schema has required fields without defaults, but it prevents making calls)
        # For our use case, we should return an empty list response if possible.
        # But a safer approach is to raise an exception indicating AI is disabled so the caller can catch it.
        raise RuntimeError("AI is explicitly disabled (llm_provider='none').")


def get_llm_provider() -> LLMProvider:
    # Factory to get the configured provider
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY must be set when llm_provider is 'gemini'.")
        return GeminiProvider()
    elif provider == "mock":
        return MockProvider(responses={"default": {}})
    elif provider == "none":
        return NoOpProvider()
    else:
        raise ValueError(f"Unknown llm_provider: {provider}")
