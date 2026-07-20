import json
from typing import TypeVar
from pydantic import BaseModel

from google import genai
from google.genai import types

from app.config import get_settings
from .base import ProviderInterface

T = TypeVar("T", bound=BaseModel)

class GeminiProvider(ProviderInterface):
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

    def generate_structured_json(self, prompt: str, schema: type[T]) -> str:
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        return response.text
