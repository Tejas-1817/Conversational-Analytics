"""Provider-aware structured-output compatibility and validation.

This module keeps provider capability decisions out of semantic-generation
services.  It converts Pydantic's reusable-definition schemas into the subset
required by constrained local runtimes, chooses safe fallback strategies, and
validates every response before it reaches business logic.
"""

from __future__ import annotations

import copy
import json
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol, TypeVar

import requests
import structlog
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)
logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ProviderCapabilities:
    """Structured-output features advertised by an LLM provider."""

    supports_json_schema: bool = False
    supports_refs: bool = False
    supports_defs: bool = False
    supports_json_mode: bool = False
    supports_function_calling: bool = False
    supports_streaming: bool = False
    supports_parallel_calls: bool = False


class StructuredOutputStrategy(StrEnum):
    NATIVE_SCHEMA = "native_schema"
    FLATTENED_SCHEMA = "flattened_schema"
    JSON_MODE = "json_mode"


class GenerationErrorKind(StrEnum):
    SCHEMA_COMPATIBILITY = "schema_compatibility"
    PROVIDER = "provider"
    VALIDATION = "validation"
    GENERATION = "generation"
    TIMEOUT = "timeout"
    NETWORK = "network"


@dataclass(frozen=True)
class StructuredOutputRequest:
    """Provider-neutral rendering instructions for a single generation call."""

    strategy: StructuredOutputStrategy
    output_schema: dict[str, Any] | None
    flattened: bool = False


class StructuredProvider(Protocol):
    """Minimal protocol used by the coordinator; concrete providers stay injectable."""

    capabilities: ProviderCapabilities
    model_name: str

    def generate_structured_json(
        self,
        prompt: str,
        schema: type[BaseModel],
        request: StructuredOutputRequest | None = None,
    ) -> str: ...


def flatten_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Inline local ``$ref`` values and remove Pydantic-only schema machinery.

    Ollama accepts ordinary object schemas but older versions reject ``$defs``
    and references.  The function is intentionally pure so it can be used for
    provider compatibility tests without a live model.
    """
    definitions = copy.deepcopy(schema.get("$defs", {}))

    def resolve(value: Any, stack: tuple[str, ...] = ()) -> Any:
        if isinstance(value, list):
            return [resolve(item, stack) for item in value]
        if not isinstance(value, dict):
            return value

        ref = value.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            name = ref.rsplit("/", 1)[-1]
            if name in stack:
                raise ValueError(f"Recursive JSON Schema reference is not supported: {name}")
            if name not in definitions:
                raise ValueError(f"JSON Schema reference does not exist: {ref}")
            resolved = resolve(definitions[name], (*stack, name))
            siblings = {key: item for key, item in value.items() if key != "$ref"}
            if siblings and isinstance(resolved, dict):
                resolved = {**resolved, **resolve(siblings, stack)}
            return resolved

        # Local models commonly reject nullable anyOf wrappers.  Preserve the
        # concrete branch; Pydantic remains the final authority on validation.
        if "anyOf" in value:
            branches = [branch for branch in value["anyOf"] if branch != {"type": "null"}]
            if len(branches) == 1:
                return resolve(branches[0], stack)

        unsupported = {"$defs", "$ref", "$schema", "title", "default", "examples"}
        return {
            key: resolve(item, stack)
            for key, item in value.items()
            if key not in unsupported
        }

    flattened = resolve(copy.deepcopy(schema))
    if not isinstance(flattened, dict):
        raise ValueError("A structured output schema must resolve to an object")
    flattened.pop("$defs", None)
    return flattened


def classify_generation_error(error: BaseException) -> GenerationErrorKind:
    """Classify failures so callers and logs can distinguish recovery paths."""
    if isinstance(error, ValidationError):
        return GenerationErrorKind.VALIDATION
    if isinstance(error, requests.exceptions.Timeout):
        return GenerationErrorKind.TIMEOUT
    if isinstance(error, requests.exceptions.ConnectionError):
        return GenerationErrorKind.NETWORK
    if isinstance(error, requests.exceptions.HTTPError):
        if error.response is not None and error.response.status_code == 400:
            return GenerationErrorKind.SCHEMA_COMPATIBILITY
        return GenerationErrorKind.PROVIDER
    return GenerationErrorKind.GENERATION


class StructuredOutputCoordinator:
    """Apply compatible schema strategies and validate output with one repair retry."""

    _strategy_cache: dict[tuple[str, str], StructuredOutputStrategy] = {}

    def _attempts(self, capabilities: ProviderCapabilities, schema: type[T]) -> list[StructuredOutputRequest]:
        native = schema.model_json_schema()
        flattened = flatten_json_schema(native)
        attempts: list[StructuredOutputRequest] = []
        if capabilities.supports_json_schema and capabilities.supports_refs and capabilities.supports_defs:
            attempts.append(StructuredOutputRequest(StructuredOutputStrategy.NATIVE_SCHEMA, native))
        if capabilities.supports_json_schema:
            attempts.append(
                StructuredOutputRequest(StructuredOutputStrategy.FLATTENED_SCHEMA, flattened, flattened=True)
            )
        if capabilities.supports_json_mode:
            attempts.append(StructuredOutputRequest(StructuredOutputStrategy.JSON_MODE, None, flattened=True))
        if not attempts:
            attempts.append(StructuredOutputRequest(StructuredOutputStrategy.JSON_MODE, None, flattened=True))
        return attempts

    @staticmethod
    def _prompt(
        prompt: str,
        request: StructuredOutputRequest,
        schema: type[T],
        repair_errors: str | None = None,
    ) -> str:
        schema_for_prompt = request.output_schema or flatten_json_schema(schema.model_json_schema())
        instruction = (
            "Return exactly one JSON object. Do not include markdown or explanation. "
            f"It must validate against this JSON Schema:\n{json.dumps(schema_for_prompt, separators=(',', ':'))}"
        )
        if repair_errors:
            instruction += f"\nThe previous response failed validation: {repair_errors}. Correct it."
        return f"{instruction}\n\nUSER PROMPT:\n{prompt}"

    def generate(self, provider: StructuredProvider, prompt: str, schema: type[T]) -> T:
        """Generate and validate a model, falling back only for schema rejections."""
        attempts = self._attempts(provider.capabilities, schema)
        cache_key = (provider.__class__.__name__, schema.__name__)
        if cache_key in self._strategy_cache:
            cached_strategy = self._strategy_cache[cache_key]
            attempts = [req for req in attempts if req.strategy == cached_strategy]
            
        last_error: BaseException | None = None
        for index, request in enumerate(attempts):
            started = time.monotonic()
            validation_retry_count = 0
            try:
                raw = provider.generate_structured_json(self._prompt(prompt, request, schema), schema, request)
                try:
                    result = schema.model_validate_json(raw)
                except ValidationError as error:
                    validation_retry_count = 1
                    logger.warning(
                        "structured_output_validation_failed",
                        provider=provider.__class__.__name__, model=provider.model_name,
                        strategy=request.strategy.value, validation_errors=error.errors(), retry_count=1,
                    )
                    repair_prompt = self._prompt(prompt, request, schema, json.dumps(error.errors()))
                    raw = provider.generate_structured_json(repair_prompt, schema, request)
                    result = schema.model_validate_json(raw)
                logger.info(
                    "structured_output_generated",
                    provider=provider.__class__.__name__, model=provider.model_name,
                    strategy=request.strategy.value,
                    schema_size=len(
                        json.dumps(request.output_schema or flatten_json_schema(schema.model_json_schema()))
                    ),
                    flattened=request.flattened, fallback_used=index > 0, retry_count=validation_retry_count,
                    generation_latency=time.monotonic() - started,
                )
                self._strategy_cache[cache_key] = request.strategy
                return result
            except Exception as error:
                kind = classify_generation_error(error)
                last_error = error
                logger.warning(
                    "structured_output_attempt_failed",
                    provider=provider.__class__.__name__, model=provider.model_name,
                    strategy=request.strategy.value, error_kind=kind.value,
                    error=str(error), fallback_used=index > 0,
                )
                if kind is not GenerationErrorKind.SCHEMA_COMPATIBILITY or index == len(attempts) - 1:
                    raise
        assert last_error is not None
        raise last_error
