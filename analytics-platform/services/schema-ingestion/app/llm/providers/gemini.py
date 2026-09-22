"""Unified Google Gemini LLM Provider with timeout, retry, and multi-model fallback."""

from __future__ import annotations

import time
from typing import TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel
import structlog

from app.config import get_settings
from app.llm.schema_adapter import ProviderCapabilities, StructuredOutputRequest, StructuredOutputStrategy
from .base import ProviderInterface

log = structlog.get_logger(__name__)
T = TypeVar("T", bound=BaseModel)


class GeminiProvider(ProviderInterface):
    """Unified Gemini provider handling client lifecycle, fallbacks, and error mapping."""

    capabilities = ProviderCapabilities(
        supports_json_schema=True,
        supports_refs=True,
        supports_defs=True,
        supports_json_mode=True,
    )

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.gemini_api_key:
            raise ValueError("gemini_api_key must be set when llm_provider is 'gemini'.")

        self.timeout_seconds = getattr(settings, "gemini_timeout_seconds", 60)
        self.client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(
                api_version="v1",
                timeout=int(self.timeout_seconds * 1000),  # 60,000 ms
            ),
        )

        self.model_name = getattr(settings, "gemini_model", "gemini-3.5-flash-lite") or "gemini-3.5-flash-lite"
        
        # Fallback candidate models if primary model is congested (503)
        fallback_str = getattr(settings, "gemini_fallback_models", "") or ""
        configured_fallbacks = [m.strip() for m in fallback_str.split(",") if m.strip()]
        
        self.candidate_models = list(
            dict.fromkeys([
                self.model_name,
                *configured_fallbacks,
                "gemini-3.5-flash-lite",
                "gemini-3.5-flash",
                "gemini-3.7-flash",
                "gemini-flash-lite-latest",
            ])
        )

    def generate_chat_completion(
        self,
        prompt: str,
        max_output_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> str:
        """Generate text/SQL completion with automatic fallback on transient 503/429 spikes."""
        started_at = time.perf_counter()
        last_error: Exception | None = None

        for model in self.candidate_models:
            try:
                config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                ) if max_output_tokens else types.GenerateContentConfig(temperature=temperature)

                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )

                raw_text = (response.text or "").strip()
                elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)

                log.info(
                    "gemini_request_completed",
                    model=model,
                    elapsed_ms=elapsed_ms,
                    prompt_chars=len(prompt),
                    response_chars=len(raw_text),
                )

                if not raw_text:
                    raise RuntimeError(f"Gemini model {model} returned an empty response.")

                return raw_text

            except Exception as exc:
                last_error = exc
                error_msg = str(exc)
                log.warning("gemini_model_attempt_failed", model=model, error=error_msg)

                # Retry on transient capacity/rate-limit errors
                if any(code in error_msg for code in ("503", "429", "404", "UNAVAILABLE", "NOT_FOUND")):
                    time.sleep(0.3)
                    continue

                raise RuntimeError(f"Gemini generation error: {exc}") from exc

        raise RuntimeError(f"All candidate Gemini models failed: {last_error}") from last_error

    def generate_structured_json(
        self,
        prompt: str,
        schema: type[T],
        request: StructuredOutputRequest | None = None,
    ) -> str:
        """Generate structured JSON adhering to the provided Pydantic schema."""
        config = {"response_mime_type": "application/json"}
        if request is None or request.strategy is not StructuredOutputStrategy.JSON_MODE:
            config["response_schema"] = request.output_schema if request else schema.model_json_schema()

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(**config),
        )
        return response.text or ""
