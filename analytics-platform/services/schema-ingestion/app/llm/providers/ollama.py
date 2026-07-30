from typing import TypeVar

import requests
import structlog
from pydantic import BaseModel

from app.config import get_settings
from app.llm.schema_adapter import ProviderCapabilities, StructuredOutputRequest, StructuredOutputStrategy

from .base import ProviderInterface

T = TypeVar("T", bound=BaseModel)
logger = structlog.get_logger(__name__)

class OllamaProvider(ProviderInterface):
    """Ollama local provider with constrained JSON Schema compatibility."""

    capabilities = ProviderCapabilities(
        supports_json_schema=True,
        supports_json_mode=True,
    )

    def __init__(self):
        settings = get_settings()
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model_name = settings.ollama_model

    def generate_chat_completion(self, prompt: str) -> str:
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.5}
        }

        response = requests.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=600.0
        )
        response.raise_for_status()
        return response.json().get("response", "")

    def generate_structured_json(
        self,
        prompt: str,
        schema: type[T],
        request: StructuredOutputRequest | None = None,
    ) -> str:
        output_format: dict | str = "json"
        if request and request.strategy is not StructuredOutputStrategy.JSON_MODE:
            output_format = request.output_schema or schema.model_json_schema()

        # Fallback to simple JSON mode if schema contains $defs (which Ollama fails on)
        if isinstance(output_format, dict) and "$defs" in output_format:
            output_format = "json"

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "format": output_format,
            "options": {"temperature": 0.0}
        }

        response = requests.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=600.0
        )
        if response.status_code >= 400:
            logger.error(
                "ollama_generate_error",
                status=response.status_code,
                body=response.text[:2000],
            )
        response.raise_for_status()

        try:
            raw_text = response.json().get("response", "").strip()
        except ValueError as e:
            print("ERROR PARSING OLLAMA HTTP RESPONSE AS JSON!")
            print("HTTP STATUS:", response.status_code)
            print("HTTP BODY:", response.text)
            raise e

        # Robustly strip markdown json blocks if the model ignored our formatting instructions
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            if len(lines) > 1 and lines[0].startswith("```"):
                lines = lines[1:]
            if len(lines) > 0 and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw_text = "\n".join(lines).strip()

        return raw_text
