from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.config import get_settings
from app.llm.schema_adapter import ProviderCapabilities, StructuredOutputRequest, StructuredOutputStrategy

from .base import ProviderInterface

T = TypeVar("T", bound=BaseModel)

class GeminiProvider(ProviderInterface):
    capabilities = ProviderCapabilities(
        supports_json_schema=True,
        supports_refs=True,
        supports_defs=True,
        supports_json_mode=True,
    )

    def __init__(self):
        settings = get_settings()
        if not settings.gemini_api_key:
            raise ValueError("gemini_api_key must be set when llm_provider is 'gemini'.")
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model_name = "gemini-2.0-flash"

    def generate_chat_completion(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
        )
        return response.text

    def generate_structured_json(
        self,
        prompt: str,
        schema: type[T],
        request: StructuredOutputRequest | None = None,
    ) -> str:
        config = {"response_mime_type": "application/json"}
        if request is None or request.strategy is not StructuredOutputStrategy.JSON_MODE:
            config["response_schema"] = request.output_schema if request else schema.model_json_schema()
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(**config),
        )
        return response.text
