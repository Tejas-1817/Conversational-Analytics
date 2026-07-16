import json

from huggingface_hub import InferenceClient
from pydantic import BaseModel
from typing import TypeVar

from app.config import get_settings
from .base import ProviderInterface

T = TypeVar("T", bound=BaseModel)

class HuggingFaceProvider(ProviderInterface):
    """
    Hugging Face LLM Provider using the official InferenceClient.
    This provider only handles network IO. Retries, caching, and validation
    are handled by the AIOrchestrator.
    """

    def __init__(self):
        settings = get_settings()
        if not settings.huggingface_api_key:
            raise ValueError("huggingface_api_key must be set when llm_provider is 'huggingface'.")
        
        self.client = InferenceClient(
            model=settings.hf_model,
            token=settings.huggingface_api_key,
            timeout=settings.hf_timeout
        )
        self.settings = settings

    def generate_chat_completion(self, prompt: str) -> str:
        response = self.client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=self.settings.hf_max_tokens,
            temperature=self.settings.hf_temperature,
            top_p=self.settings.hf_top_p
        )
        return response.choices[0].message.content

    def generate_structured_json(self, prompt: str, schema: type[T]) -> str:
        # Note: Depending on the specific Hugging Face model and endpoint, 
        # structured JSON generation can be supported natively via grammar or json mode.
        # Here we use json mode if supported, or prompt engineering.
        # The inference client supports `response_format={"type": "json_object"}` 
        # on supported models.
        
        system_prompt = (
            "You are a helpful assistant designed to output strict JSON. "
            f"Your output must adhere exactly to the following JSON schema:\n{json.dumps(schema.model_json_schema())}"
        )
        
        response = self.client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=self.settings.hf_max_tokens,
            temperature=self.settings.hf_temperature,
            top_p=self.settings.hf_top_p
        )
        return response.choices[0].message.content
