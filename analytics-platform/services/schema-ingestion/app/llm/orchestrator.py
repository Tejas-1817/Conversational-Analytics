import time
import os
import hashlib
import json
from typing import TypeVar, Any

import redis
import structlog
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_not_exception_type
from rq.timeouts import JobTimeoutException

from .registry import get_llm_provider_from_config

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
        retry=retry_if_not_exception_type(JobTimeoutException),
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
            # Self-correction loop
            max_attempts = 3
            last_exception = None
            current_prompt = prompt
            raw_response = ""
            
            for attempt in range(max_attempts):
                try:
                    # Execute provider call
                    raw_response = self.provider.generate_structured_json(current_prompt, schema)
                    parsed_result = schema.model_validate_json(raw_response)
                    break  # Success!
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning("ai.generation.validation_retry", attempt=attempt+1, schema=schema_name, error=str(e))
                        current_prompt = f"{prompt}\n\nIMPORTANT PREVIOUS ATTEMPT FAILED:\nYou generated this invalid JSON:\n{raw_response}\n\nValidation Error:\n{str(e)}\n\nPlease precisely fix the JSON to match the schema requirements. Only output valid JSON."
                    else:
                        print(f"FAILED TO VALIDATE JSON AFTER {max_attempts} ATTEMPTS:\n{repr(raw_response)}")
                        raise last_exception
            
            # Set cache
            try:
                self.redis.set(cache_key, raw_response, ex=86400) # 1 day TTL
            except redis.RedisError:
                pass

            # Log telemetry
            latency = time.time() - start_time
            logger.info(
                "ai.generation.success",
                provider=self.provider.__class__.__name__,
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
                latency=latency,
                error=str(e),
                schema=schema_name
            )
            raise

    @retry(
        stop=stop_after_attempt(3), 
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_not_exception_type(JobTimeoutException),
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
