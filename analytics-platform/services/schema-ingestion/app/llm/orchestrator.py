import hashlib
import json
import os
import time
from typing import TypeVar

import redis
import requests
import structlog
from pydantic import BaseModel, ValidationError
from rq.timeouts import JobTimeoutException
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from .registry import get_llm_provider_from_config
from .schema_adapter import StructuredOutputCoordinator, classify_generation_error


def should_retry_llm(exc: BaseException) -> bool:
    if isinstance(exc, JobTimeoutException):
        return False
    if isinstance(exc, ValidationError):
        return False
    if isinstance(exc, json.JSONDecodeError):
        return False
    if isinstance(exc, requests.exceptions.HTTPError):
        if exc.response is not None:
            status_code = exc.response.status_code
            if status_code == 400:
                return False
            if status_code == 429 or status_code >= 500:
                return True
    if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
        return True
    return False

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

class AIOrchestrator:
    """
    Enterprise AI Orchestrator.
    Handles telemetry, retries, caching, and validation.
    """
    def __init__(self):
        # We lazy load or inject the provider
        self._provider = None
        self.structured_output = StructuredOutputCoordinator()
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis = redis.from_url(redis_url)

    @property
    def provider(self):
        if not self._provider:
            self._provider = get_llm_provider_from_config()
        return self._provider

    def _get_cache_key(self, prompt: str, schema_name: str) -> str:
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        return f"ai_cache:{schema_name}:{prompt_hash}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception(should_retry_llm),
        reraise=True
    )
    def generate_structured(self, prompt: str, schema: type[T]) -> T:
        """
        Generates a structured response with strict Pydantic validation, retries, and telemetry.
        """
        start_time = time.time()
        schema_name = schema.__name__
        cache_key = self._get_cache_key(prompt, schema_name)

        # Check cache
        try:
            cached = self.redis.get(cache_key)
            if cached:
                latency = time.time() - start_time
                logger.info(
                    "ai.generation.cache_hit",
                    schema=schema_name,
                    latency=latency
                )
                return schema.model_validate_json(cached.decode("utf-8"))
        except redis.RedisError:
            pass # Fallback if redis is down

        try:
            # Compatibility selection, fallback, and Pydantic validation are kept
            # below the business layer and apply consistently to every provider.
            parsed_result = self.structured_output.generate(self.provider, prompt, schema)

            # Set cache
            try:
                self.redis.set(cache_key, parsed_result.model_dump_json(), ex=86400) # 1 day TTL
            except redis.RedisError:
                pass

            # Log telemetry
            latency = time.time() - start_time
            logger.info(
                "ai.generation.success",
                provider=self.provider.__class__.__name__,
                model=self.provider.model_name,
                latency=latency,
                schema=schema_name
            )
            return parsed_result

        except JobTimeoutException:
            raise
        except Exception as e:
            latency = time.time() - start_time
            logger.error(
                "ai.generation.error",
                provider=self.provider.__class__.__name__,
                model=self.provider.model_name,
                latency=latency,
                error=str(e),
                error_kind=classify_generation_error(e).value,
                schema=schema_name
            )
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception(should_retry_llm),
        reraise=True
    )
    def generate_chat(self, prompt: str) -> str:
        """
        Generates a standard text chat response.
        """
        start_time = time.time()
        cache_key = self._get_cache_key(prompt, "chat")

        try:
            cached = self.redis.get(cache_key)
            if cached:
                latency = time.time() - start_time
                logger.info(
                    "ai.generation.cache_hit",
                    type="chat",
                    latency=latency
                )
                return cached.decode("utf-8")
        except redis.RedisError:
            pass

        try:
            response = self.provider.generate_chat_completion(prompt)

            try:
                self.redis.set(cache_key, response, ex=86400)
            except redis.RedisError:
                pass

            latency = time.time() - start_time
            logger.info(
                "ai.generation.success",
                provider=self.provider.__class__.__name__,
                latency=latency,
                type="chat"
            )
            return response
        except JobTimeoutException:
            raise
        except Exception as e:
            latency = time.time() - start_time
            logger.error(
                "ai.generation.error",
                provider=self.provider.__class__.__name__,
                latency=latency,
                error=str(e),
                type="chat"
            )
            raise

ai_orchestrator = AIOrchestrator()
