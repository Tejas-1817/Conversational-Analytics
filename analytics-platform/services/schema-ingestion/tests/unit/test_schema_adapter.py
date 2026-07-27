"""Offline tests for provider-aware structured output compatibility."""

import json
from typing import Any

import requests
from pydantic import BaseModel

from app.llm.providers.gemini import GeminiProvider
from app.llm.providers.ollama import OllamaProvider
from app.llm.schema_adapter import (
    ProviderCapabilities,
    StructuredOutputCoordinator,
    StructuredOutputRequest,
    StructuredOutputStrategy,
    flatten_json_schema,
)


class _Address(BaseModel):
    city: str


class _Customer(BaseModel):
    name: str
    address: _Address


class _RecordingProvider:
    """Injectable provider double that records the selected compatibility strategy."""

    model_name = "test-model"

    def __init__(self, capabilities: ProviderCapabilities, responses: list[Any]) -> None:
        self.capabilities = capabilities
        self.responses = iter(responses)
        self.requests: list[StructuredOutputRequest | None] = []
        self.prompts: list[str] = []

    def generate_structured_json(
        self,
        prompt: str,
        schema: type[BaseModel],
        request: StructuredOutputRequest | None = None,
    ) -> str:
        self.prompts.append(prompt)
        self.requests.append(request)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return json.dumps(response)


def _bad_request() -> requests.HTTPError:
    response = requests.Response()
    response.status_code = 400
    return requests.HTTPError("schema rejected", response=response)


def test_flatten_json_schema_inlines_pydantic_defs_and_refs() -> None:
    flattened = flatten_json_schema(_Customer.model_json_schema())
    serialized = json.dumps(flattened)

    assert "$defs" not in flattened
    assert "$ref" not in serialized
    assert flattened["properties"]["address"]["properties"]["city"]["type"] == "string"
    assert flattened["required"] == ["name", "address"]


def test_ollama_capabilities_choose_flattened_schema_without_provider_name_branching() -> None:
    provider = _RecordingProvider(
        ProviderCapabilities(supports_json_schema=True, supports_json_mode=True),
        [{"name": "Ada", "address": {"city": "Pune"}}],
    )

    result = StructuredOutputCoordinator().generate(provider, "Create customer", _Customer)

    assert result.address.city == "Pune"
    assert provider.requests[0].strategy is StructuredOutputStrategy.FLATTENED_SCHEMA
    assert provider.requests[0].flattened is True


def test_schema_rejection_falls_back_from_flattened_schema_to_json_mode() -> None:
    provider = _RecordingProvider(
        ProviderCapabilities(supports_json_schema=True, supports_json_mode=True),
        [_bad_request(), {"name": "Ada", "address": {"city": "Pune"}}],
    )

    result = StructuredOutputCoordinator().generate(provider, "Create customer", _Customer)

    assert result.name == "Ada"
    assert [request.strategy for request in provider.requests] == [
        StructuredOutputStrategy.FLATTENED_SCHEMA,
        StructuredOutputStrategy.JSON_MODE,
    ]


def test_invalid_response_is_repaired_once_before_returning_validated_model() -> None:
    provider = _RecordingProvider(
        ProviderCapabilities(supports_json_schema=True, supports_refs=True, supports_defs=True),
        [{"name": 123, "address": {}}, {"name": "Ada", "address": {"city": "Pune"}}],
    )

    result = StructuredOutputCoordinator().generate(provider, "Create customer", _Customer)

    assert result.name == "Ada"
    assert len(provider.requests) == 2
    assert "previous response failed validation" in provider.prompts[1].lower()


def test_existing_provider_capabilities_describe_ollama_and_gemini_schema_support() -> None:
    assert OllamaProvider.capabilities.supports_json_schema
    assert not OllamaProvider.capabilities.supports_refs
    assert GeminiProvider.capabilities.supports_json_schema
    assert GeminiProvider.capabilities.supports_defs
