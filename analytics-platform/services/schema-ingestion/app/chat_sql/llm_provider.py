"""LLM Provider — Telemetry Instrumentated & Audited.

Calls local Ollama HTTP completion endpoint to generate raw PostgreSQL SQL queries.
Instruments request timing, prompt statistics, raw response logging, failure taxonomy,
and diagnostic report logging.
"""
from datetime import datetime, timezone
import re
import time
from typing import Any, Dict, Optional
import requests
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)


class LLMProvider:
    """Ollama local LLM text completion provider with production telemetry instrumentation."""

    def __init__(self):
        settings = get_settings()
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model_name = settings.ollama_model

    def generate_sql(self, prompt: str, question: str = "") -> str:
        t_start_total = time.time()
        req_timestamp = datetime.now(timezone.utc).isoformat()
        url = f"{self.base_url}/api/generate"
        models_to_try = list(dict.fromkeys([self.model_name.strip(), "gemma3:4b"]))

        prompt_chars = len(prompt)
        estimated_tokens = prompt_chars // 4
        question_chars = len(question)
        schema_chars = max(0, prompt_chars - question_chars)

        log.info(
            "ollama_prompt_statistics",
            request_timestamp=req_timestamp,
            prompt_length_chars=prompt_chars,
            estimated_tokens=estimated_tokens,
            question_length_chars=question_chars,
            schema_size_chars=schema_chars
        )

        last_error = None
        last_error_class = None

        for model in models_to_try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "top_p": 0.1,
                    "num_predict": 2048
                }
            }

            t_http_start = time.time()
            http_status_code = None
            raw_text = ""
            error_class = None

            try:
                log.info(
                    "requesting_llm_sql_completion",
                    model=model,
                    request_timestamp=req_timestamp,
                    url=url,
                    payload_options=payload["options"]
                )

                resp = requests.post(url, json=payload, timeout=600)
                t_http_end = time.time()
                stage_http_ms = (t_http_end - t_http_start) * 1000.0
                http_status_code = resp.status_code

                t_parse_start = time.time()
                resp.raise_for_status()
                data = resp.json()
                t_parse_end = time.time()
                stage_parse_ms = (t_parse_end - t_parse_start) * 1000.0

                raw_text = data.get("response", "").strip()
                raw_chars = len(raw_text)

                # Log Complete Raw Uncleaned Response
                log.info(
                    "ollama_raw_response_received",
                    model=model,
                    http_status_code=http_status_code,
                    raw_response_length=raw_chars,
                    stage_http_ms=round(stage_http_ms, 2),
                    stage_json_ms=round(stage_parse_ms, 2),
                    raw_ollama_response=raw_text
                )

                if not raw_text:
                    error_class = "LLM_EMPTY_RESPONSE"
                    last_error = "Ollama returned empty completion text."
                    log.warning("llm_attempt_empty_response", model=model, error_class=error_class)
                    continue

                # Stage 4: SQL Cleaning & Extraction
                t_clean_start = time.time()
                cleaned_sql = self._clean_sql_output(raw_text)
                t_clean_end = time.time()
                stage_clean_ms = (t_clean_end - t_clean_start) * 1000.0
                cleaned_chars = len(cleaned_sql)

                # Validate non-empty and starts with SELECT or WITH
                if not cleaned_sql or not (cleaned_sql.upper().startswith("SELECT") or cleaned_sql.upper().startswith("WITH")):
                    error_class = "LLM_INVALID_SQL"
                    last_error = f"Ollama response could not be parsed into a valid SELECT query. Cleaned: '{cleaned_sql}'"
                    log.warning(
                        "llm_attempt_invalid_sql",
                        model=model,
                        error_class=error_class,
                        cleaned_sql=cleaned_sql
                    )
                    continue

                t_total_end = time.time()
                total_latency_s = t_total_end - t_start_total

                # Diagnostic Report
                log.info(
                    "ollama_diagnostic_report",
                    model=model,
                    status="SUCCESS",
                    http_status_code=http_status_code,
                    error_class=None,
                    total_latency_s=round(total_latency_s, 2),
                    stage_http_ms=round(stage_http_ms, 2),
                    stage_clean_ms=round(stage_clean_ms, 2),
                    prompt_chars=prompt_chars,
                    estimated_tokens=estimated_tokens,
                    raw_response_chars=raw_chars,
                    cleaned_sql_chars=cleaned_chars,
                    generated_sql=cleaned_sql,
                    validation_status="PASSED"
                )

                return cleaned_sql

            except requests.exceptions.ReadTimeout as e:
                error_class = "LLM_TIMEOUT"
                last_error = f"HTTP ReadTimeout (timeout=120s): {e}"
                last_error_class = error_class
                log.warning("llm_model_attempt_timeout", model=model, error_class=error_class, error=str(e))
            except requests.exceptions.ConnectionError as e:
                error_class = "LLM_CONNECTION_FAILED"
                last_error = f"ConnectionRefused / Unreachable: {e}"
                last_error_class = error_class
                log.warning("llm_model_attempt_connection_failed", model=model, error_class=error_class, error=str(e))
            except Exception as e:
                error_class = "LLM_INVALID_RESPONSE"
                last_error = f"HTTP Error or JSON Exception: {e}"
                last_error_class = error_class
                log.warning("llm_model_attempt_invalid_response", model=model, error_class=error_class, error=str(e))

        t_total_fail = time.time()
        total_latency_fail_s = t_total_fail - t_start_total

        log.error(
            "ollama_llm_completion_failed",
            error_class=last_error_class,
            last_error=str(last_error),
            total_latency_s=round(total_latency_fail_s, 2)
        )

        raise RuntimeError(f"LLM completion request failed for all models: {last_error}")

    def _clean_sql_output(self, raw_text: str) -> str:
        """Removes markdown backticks, thinking blocks, explanations, or extra formatting."""
        cleaned = raw_text.strip()
        # Remove thinking blocks if present <thought>...</thought>
        cleaned = re.sub(r"<thought>.*?</thought>", "", cleaned, flags=re.DOTALL).strip()

        if "```sql" in cleaned:
            match = re.search(r"```sql\s*(.*?)\s*```", cleaned, re.DOTALL | re.IGNORECASE)
            if match:
                cleaned = match.group(1).strip()
        elif "```" in cleaned:
            match = re.search(r"```\s*(.*?)\s*```", cleaned, re.DOTALL)
            if match:
                cleaned = match.group(1).strip()

        # Remove trailing explanations if LLM appended text after semicolon
        if ";" in cleaned:
            cleaned = cleaned.split(";")[0].strip() + ";"

        return cleaned

    def generate_text(self, prompt: str, max_tokens: int = 256, timeout: int = 30) -> str:
        """Generates arbitrary natural language text from Ollama WITHOUT any SQL validation."""
        url = f"{self.base_url}/api/generate"
        models_to_try = list(dict.fromkeys([self.model_name.strip(), "gemma4:12b"]))

        for model in models_to_try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": max_tokens
                }
            }
            try:
                resp = requests.post(url, json=payload, timeout=timeout)
                resp.raise_for_status()
                data = resp.json()
                raw_text = data.get("response", "").strip()
                if raw_text:
                    cleaned = re.sub(r"<thought>.*?</thought>", "", raw_text, flags=re.DOTALL).strip()
                    cleaned = cleaned.strip('"').strip("'")
                    return cleaned
            except Exception as e:
                log.warning("llm_generate_text_attempt_failed", model=model, error=str(e))

        raise RuntimeError("LLM text generation failed for all models.")
