"""LLM Provider.

Calls local Ollama HTTP completion endpoint to generate raw PostgreSQL SQL queries.
"""
import re
import requests
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)


class LLMProvider:
    """Ollama local LLM text completion provider."""

    def __init__(self):
        settings = get_settings()
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model_name = settings.ollama_model

    def generate_sql(self, prompt: str) -> str:
        url = f"{self.base_url}/api/generate"
        models_to_try = ["qwen2.5:7b", self.model_name]

        last_error = None
        for model in models_to_try:
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "top_p": 0.1,
                    "num_predict": 128,
                    "stop": ["\n\n"]
                }
            }
            try:
                log.info("requesting_llm_sql_completion", model=model)
                resp = requests.post(url, json=payload, timeout=180)
                resp.raise_for_status()
                data = resp.json()
                raw_text = data.get("response", "").strip()
                if raw_text:
                    return self._clean_sql_output(raw_text)
            except Exception as e:
                log.warning("llm_model_attempt_failed", model=model, error=str(e))
                last_error = e

        raise RuntimeError(f"LLM completion request failed for all models: {last_error}")

    def _clean_sql_output(self, raw_text: str) -> str:
        """Removes markdown backticks, explanations, or extra formatting."""
        cleaned = raw_text.strip()
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
