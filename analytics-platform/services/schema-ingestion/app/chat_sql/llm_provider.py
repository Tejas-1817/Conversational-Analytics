"""Multi-provider LLM connector for SQL generation, review, correction, and text output."""

from __future__ import annotations

import json
import re
import time

import requests
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)


class LLMProviderError(RuntimeError):
    """Base LLM provider error."""


class LLMTimeoutError(LLMProviderError):
    """LLM did not produce output before the configured deadline."""


class LLMUnavailableError(LLMProviderError):
    """LLM could not be reached."""


class LLMProvider:
    """Generate, review, and synthesize SQL/text using Gemini or Ollama."""

    def __init__(self) -> None:
        settings = get_settings()
        self.provider = (settings.llm_provider or "ollama").strip().lower()

        # --- Gemini Setup ---
        self.gemini_client = None
        self.gemini_model = getattr(settings, "gemini_model", "gemini-3.5-flash-lite") or "gemini-3.5-flash-lite"
        # self.gemini_sql_max_output_tokens = settings.gemini_sql_max_output_tokens
        self.gemini_sql_max_output_tokens = getattr(settings, "gemini_sql_max_output_tokens", 768)
        self.gemini_text_max_output_tokens = getattr(settings, "gemini_text_max_output_tokens", 1500)

        self.gemini_fallback_models = [
            model.strip()
            for model in settings.gemini_fallback_models.split(",")
            if model.strip()
        ]
        
        if self.provider == "gemini":
            if not settings.gemini_api_key:
                raise ValueError("GEMINI_API_KEY must be configured in .env when LLM_PROVIDER is 'gemini'.")
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=settings.gemini_api_key)
            except ImportError:
                raise ImportError(
                    "The 'google-genai' package is required for Gemini support. "
                    "Run 'pip install google-genai' to install it."
                )

            from google.genai import types

            self.gemini_client = genai.Client(
                api_key=settings.gemini_api_key,
                http_options=types.HttpOptions(
                    api_version="v1",
                    timeout=int(settings.gemini_timeout_seconds * 1000),  # 60,000 ms
                ),

            )

        # --- Ollama Setup (Default / Fallback) ---
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model_name = settings.ollama_model.strip()
        self.fallback_model = settings.ollama_fallback_model.strip()
        self.keep_alive = settings.ollama_keep_alive.strip()
        self.http = requests.Session()

        self.num_ctx = settings.ollama_num_ctx
        self.num_predict = settings.ollama_num_predict
        self.timeout_seconds = settings.ollama_timeout_seconds
        self.sql_review_enabled = settings.ollama_sql_review_enabled

    @staticmethod
    def _dialect_rules(dialect: str) -> tuple[str, str]:
        normalized = dialect.lower()

        if normalized == "mssql":
            return (
                "Microsoft SQL Server T-SQL",
                """
- Never use LIMIT or PostgreSQL DATE_TRUNC.
- Use TOP (N) or OFFSET ... FETCH for row limits.
- Prefer joining dim_date for year, month number, and month name.
- When necessary, use DATETRUNC, DATEFROMPARTS, YEAR, and MONTH.
- Use NULLIF(denominator, 0) for division.
""".strip(),
            )

        if normalized == "mysql":
            return (
                "MySQL",
                """
- Use LIMIT for row limits.
- Use DATE_FORMAT or YEAR and MONTH for monthly grouping.
- Never use PostgreSQL DATE_TRUNC.
- Use NULLIF(denominator, 0) for division.
""".strip(),
            )

        return (
            "PostgreSQL",
            """
- Use LIMIT for row limits.
- Use DATE_TRUNC for time grouping.
- Use NULLIF(denominator, 0) for division.
""".strip(),
        )

    def _models_to_try(self) -> list[str]:
        return [
            model
            for model in dict.fromkeys([self.model_name, self.fallback_model])
            if model
        ]

    def _request_gemini(
        self,
        prompt: str,
        max_output_tokens: int | None = None,
        temperature: float = 0.0,
    ) -> str:
        """Execute request using Gemini with automatic multi-model fallback on 503/429 errors."""
        if not self.gemini_client:
            raise LLMUnavailableError("Gemini client is not initialized.")

        started_at = time.perf_counter()
        
        # Primary model followed by high-availability fallbacks
        candidate_models = list(
            dict.fromkeys([
                self.gemini_model,
                *self.gemini_fallback_models,
            ])
        )

        last_error: Exception | None = None

        for model in candidate_models:
            try:
                from google.genai import types

                config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                ) if max_output_tokens else types.GenerateContentConfig(temperature=temperature)

                response = self.gemini_client.models.generate_content(
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
                    raise LLMProviderError(f"Model {model} returned an empty response.")

                return raw_text

            except Exception as exc:
                last_error = exc
                error_msg = str(exc)
                log.warning(
                    "gemini_model_attempt_failed",
                    model=model,
                    error=error_msg,
                )

                # If transient 503 / 429 / 404, quickly try next candidate model
                if any(code in error_msg for code in ("503", "429", "404", "UNAVAILABLE", "NOT_FOUND")):
                    time.sleep(0.3)
                    continue
                
                # For critical auth errors, fail immediately
                raise LLMProviderError(f"Gemini generation error: {exc}") from exc

        raise LLMProviderError(f"All candidate Gemini models failed: {last_error}") from last_error

    def _request_ollama(
        self,
        *,
        prompt: str,
        model: str,
        num_predict: int,
        temperature: float,
        timeout: int,
    ) -> str:
        """Execute one non-streaming Ollama request."""
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": temperature,
                "top_p": 0.1,
                "num_ctx": self.num_ctx,
                "num_predict": num_predict,
            },
        }

        started_at = time.perf_counter()
        response_parts: list[str] = []
        final_chunk: dict = {}

        with self.http.post(
            url,
            json=payload,
            stream=True,
            timeout=(10, timeout),
        ) as response:
            response.raise_for_status()
            response.encoding = "utf-8"

            deadline = time.monotonic() + timeout

            for line in response.iter_lines(decode_unicode=True):
                if time.monotonic() > deadline:
                    raise LLMTimeoutError(
                        f"Ollama exceeded the {timeout}-second total deadline."
                    )

                if not line:
                    continue

                chunk = json.loads(line)

                if chunk.get("error"):
                    raise RuntimeError(f"Ollama generation failed: {chunk['error']}")

                generated_text = chunk.get("response")
                if generated_text:
                    response_parts.append(str(generated_text))

                if chunk.get("done"):
                    final_chunk = chunk

        raw_text = "".join(response_parts).strip()
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)

        log.info(
            "ollama_request_completed",
            model=model,
            elapsed_ms=elapsed_ms,
            prompt_chars=len(prompt),
            estimated_prompt_tokens=len(prompt) // 4,
            prompt_eval_count=final_chunk.get("prompt_eval_count"),
            eval_count=final_chunk.get("eval_count"),
            response_chars=len(raw_text),
        )

        if not raw_text:
            raise RuntimeError("Ollama returned an empty response.")

        return raw_text

    def generate_sql(
        self,
        prompt: str,
        question: str = "",
        dialect: str = "postgres",
    ) -> str:
        """Generate one SQL query or UNANSWERABLE."""
        # 1. Gemini Path
        if self.provider == "gemini":
            log.info(
                "requesting_gemini_sql_generation",
                model=self.gemini_model,
                question_chars=len(question),
                prompt_chars=len(prompt),
            )
            raw_text = self._request_gemini(
                prompt=prompt,
                max_output_tokens=self.gemini_sql_max_output_tokens,
                temperature=0.0,
            )
            cleaned_sql = self._clean_sql_output(raw_text, dialect=dialect)

            if cleaned_sql.upper() == "UNANSWERABLE":
                return "UNANSWERABLE"

            if not cleaned_sql.upper().startswith(("SELECT", "WITH")):
                raise LLMProviderError(
                    f"Gemini returned neither SELECT/WITH SQL nor UNANSWERABLE: {cleaned_sql!r}"
                )

            log.info("gemini_sql_generated", model=self.gemini_model, sql_chars=len(cleaned_sql))
            return cleaned_sql

        # 2. Ollama Path
        last_error: Exception | None = None
        for model in self._models_to_try():
            try:
                log.info(
                    "requesting_ollama_sql_generation",
                    model=model,
                    question_chars=len(question),
                    prompt_chars=len(prompt),
                    estimated_prompt_tokens=len(prompt) // 4,
                    num_ctx=self.num_ctx,
                    num_predict=self.num_predict,
                )

                raw_text = self._request_ollama(
                    prompt=prompt,
                    model=model,
                    num_predict=self.num_predict,
                    temperature=0.0,
                    timeout=self.timeout_seconds,
                )

                cleaned_sql = self._clean_sql_output(raw_text, dialect=dialect)

                if cleaned_sql.upper() == "UNANSWERABLE":
                    return "UNANSWERABLE"

                if not cleaned_sql.upper().startswith(("SELECT", "WITH")):
                    raise RuntimeError(
                        f"Ollama returned neither SELECT/WITH SQL nor UNANSWERABLE: {cleaned_sql!r}"
                    )

                log.info("ollama_sql_generated", model=model, sql_chars=len(cleaned_sql))
                return cleaned_sql

            except requests.exceptions.Timeout as exc:
                last_error = exc
                log.warning("ollama_sql_timeout", model=model, timeout_seconds=self.timeout_seconds, error=str(exc))
            except requests.exceptions.ConnectionError as exc:
                last_error = exc
                log.warning("ollama_connection_failed", model=model, base_url=self.base_url, error=str(exc))
            except Exception as exc:
                last_error = exc
                log.warning("ollama_sql_attempt_failed", model=model, error_type=type(exc).__name__, error=str(exc))

        if isinstance(last_error, requests.exceptions.Timeout):
            raise LLMTimeoutError("Ollama timed out for every configured model.") from last_error
        if isinstance(last_error, requests.exceptions.ConnectionError):
            raise LLMUnavailableError("Unable to connect to Ollama.") from last_error

        raise LLMProviderError(f"SQL generation failed for all models: {last_error}") from last_error

    def _clean_sql_output(
        self,
        raw_text: str,
        dialect: str = "postgres",
    ) -> str:
        """Remove reasoning wrappers, code fences, and normalize SQL output."""
        cleaned = (raw_text or "").strip()

        # Remove thoughts (<think>...</think>)
        cleaned = re.sub(
            r"<(?:think|thought)>.*?</(?:think|thought)>",
            "",
            cleaned,
            flags=re.DOTALL | re.IGNORECASE,
        ).strip()

        # Remove markdown code blocks
        cleaned = re.sub(
            r"```(?:postgresql|postgres|sql|tsql|mysql)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = cleaned.replace("```", "").strip()

        if re.fullmatch(r"UNANSWERABLE[.!]?", cleaned, flags=re.IGNORECASE):
            return "UNANSWERABLE"

        match = re.search(r"\b(SELECT|WITH)\b", cleaned, flags=re.IGNORECASE)
        if not match:
            return cleaned

        cleaned = cleaned[match.start():].strip()

        try:
            import sqlglot

            sqlglot_dialects = {
                "postgres": "postgres",
                "mysql": "mysql",
                "mssql": "tsql",
                "excel": "sqlite",
            }

            glot_dialect = sqlglot_dialects.get(dialect.lower(), "postgres")
            statements = sqlglot.parse(cleaned, read=glot_dialect)

            if len(statements) == 1 and statements[0] is not None:
                return statements[0].sql(dialect=glot_dialect, pretty=False)
        except Exception:
            pass

        return cleaned

    def review_sql(
        self,
        *,
        question: str,
        candidate_sql: str,
        schema_text: str,
        domain_context: str = "",
        dialect: str = "postgres",
    ) -> str:
        """Review and correct candidate SQL before execution."""
        if not self.sql_review_enabled:
            return candidate_sql

        if candidate_sql.strip().upper() == "UNANSWERABLE":
            return "UNANSWERABLE"

        dialect_name, dialect_rules = self._dialect_rules(dialect)

        review_prompt = f"""You are the final {dialect_name} SQL reviewer.

DIALECT RULES:
{dialect_rules}

Review the candidate query against the physical schema and user question.

REVIEW RULES:
- Every physical table and column must exist in DATABASE SCHEMA.
- The query must answer the complete USER QUESTION.
- Joins must use declared relationships.
- Aggregations must preserve the correct grain.
- Return exactly one read-only SELECT or WITH query.
- Return UNANSWERABLE if the schema cannot answer the question.
- Return SQL or UNANSWERABLE only.

BUSINESS CONTEXT:
{domain_context or "None"}

DATABASE SCHEMA:
{schema_text}

USER QUESTION:
{question}

CANDIDATE SQL:
{candidate_sql}

FINAL REVIEWED SQL:"""

        log.info(
            "reviewing_sql",
            provider=self.provider,
            question_chars=len(question),
            candidate_sql_chars=len(candidate_sql),
            schema_chars=len(schema_text),
        )

        return self.generate_sql(
            review_prompt,
            question=question,
            dialect=dialect,
        )

    def refine_sql(
        self,
        *,
        question: str,
        failed_sql: str,
        error_message: str,
        schema_text: str,
        dialect: str = "postgres",
    ) -> str:
        """Correct SQL using the exact database execution error."""
        dialect_name, dialect_rules = self._dialect_rules(dialect)

        correction_prompt = f"""You are a {dialect_name} SQL correction engine.

DIALECT RULES:
{dialect_rules}

Correct the failed query using only the physical schema and database error.

RULES:
- Return exactly one read-only SELECT or WITH query.
- Use only tables and columns declared in DATABASE SCHEMA.
- Correct the exact syntax, schema, column, join, grouping, or type error.
- Preserve the user's requested metric, filters, dimensions, and ordering.
- Do not add unsupported assumptions.
- Return UNANSWERABLE if a reliable correction is impossible.
- Return SQL or UNANSWERABLE only.
- Do not return Markdown, explanation, comments, or reasoning.
- If DATABASE ERROR says a function does not exist, never reuse that function.
- DATE_BUCKET and TIME_BUCKET do not exist.
- If aggregates and non-aggregate expressions are selected together, add the required GROUP BY expressions.
- Do not repeat any SQL already rejected during this correction attempt.

DATABASE SCHEMA:
{schema_text}

USER QUESTION:
{question}

FAILED SQL:
{failed_sql}

DATABASE ERROR:
{error_message}

CORRECTED SQL:"""

        log.info(
            "refining_failed_sql",
            provider=self.provider,
            question_chars=len(question),
            failed_sql_chars=len(failed_sql),
            error_chars=len(error_message),
        )

        return self.generate_sql(
            correction_prompt,
            question=question,
            dialect=dialect,
        )

    def generate_text(
        self,
        prompt: str,
        max_tokens: int = 1500,
        timeout: int | None = None,
    ) -> str:
        """Generate grounded natural-language text without SQL cleaning."""
        # 1. Gemini Path
        if self.provider == "gemini":
            log.info(
                "requesting_gemini_text_generation",
                model=self.gemini_model,
                prompt_chars=len(prompt),
                max_tokens=max_tokens,
            )
            return self._request_gemini(
                prompt=prompt,
                max_output_tokens=min(
                    max_tokens,
                    self.gemini_text_max_output_tokens,
                ),
                temperature=0.2,
            )

        # 2. Ollama Path
        request_timeout = timeout or self.timeout_seconds
        last_error: Exception | None = None

        for model in self._models_to_try():
            try:
                log.info(
                    "requesting_ollama_text_generation",
                    model=model,
                    prompt_chars=len(prompt),
                    estimated_prompt_tokens=len(prompt) // 4,
                    num_ctx=self.num_ctx,
                    num_predict=max_tokens,
                    timeout_seconds=request_timeout,
                )

                return self._request_ollama(
                    prompt=prompt,
                    model=model,
                    num_predict=max_tokens,
                    temperature=0.2,
                    timeout=request_timeout,
                )

            except Exception as exc:
                last_error = exc
                log.warning("ollama_text_attempt_failed", model=model, error_type=type(exc).__name__, error=str(exc))

        if isinstance(last_error, requests.exceptions.Timeout):
            raise LLMTimeoutError("Ollama text generation timed out.") from last_error

        if isinstance(last_error, requests.exceptions.ConnectionError):
            raise LLMUnavailableError("Unable to connect to Ollama.") from last_error

        raise LLMProviderError(f"Text generation failed for all models: {last_error}") from last_error

    def plan_multi_queries(
        self,
        question: str,
        schema_text: str,
        dialect: str = "postgres",
    ) -> list[dict[str, str]]:
        """Decomposes a broad question into 2-3 sub-queries using Gemini."""
        from app.chat_sql.prompt_builder import PromptBuilder

        prompt = PromptBuilder.build_multi_query_plan_prompt(
            question=question,
            schema_text=schema_text,
            dialect=dialect,
        )
        try:
            raw_response = self.generate_text(prompt=prompt)
            # Clean possible markdown fence code blocks
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_response.strip(), flags=re.MULTILINE)
            plan = json.loads(cleaned)
            if isinstance(plan, list):
                return [q for q in plan if isinstance(q, dict) and "sql" in q]
        except Exception as exc:
            log.warning("multi_query_planning_failed", error=str(exc))
        return []
