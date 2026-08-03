"""Chat Service.

Orchestrates SchemaProvider, PromptBuilder, LLMProvider, and SQLValidator
to handle Text-to-SQL requests.
"""
from datetime import datetime, timezone
from typing import Any, Dict

import structlog

from app.chat_sql.answer_synthesizer import AnswerSynthesizer
from app.chat_sql.llm_provider import LLMProvider
from app.chat_sql.prompt_builder import PromptBuilder
from app.chat_sql.schema_provider import SchemaProvider
from app.chat_sql.sql_executor import SQLExecutor
from app.chat_sql.sql_validator import SQLValidator

log = structlog.get_logger(__name__)


class ChatService:
    """Text-to-SQL & Analytics Chat Service."""

    def __init__(self):
        self.schema_provider = SchemaProvider()
        self.prompt_builder = PromptBuilder()
        self.llm_provider = LLMProvider()
        self.sql_validator = SQLValidator()
        self.sql_executor = SQLExecutor()
        self.answer_synthesizer = AnswerSynthesizer()

    def process_text_to_sql(self, question: str) -> Dict[str, Any]:
        """Loads connected database schema, prompts LLM, executes SQL, synthesizes answer, and returns DTO."""
        # 1. Fetch live introspected PostgreSQL schema
        db_name, ddl, catalog = self.schema_provider.get_connected_schema()

        # 2. Build anti-hallucination prompt with active DDL
        prompt = self.prompt_builder.build_prompt(
            question=question,
            ddl=ddl,
            database_name=db_name,
            catalog=catalog
        )

        # 3. Call LLM for raw PostgreSQL SQL generation
        try:
            raw_sql = self.llm_provider.generate_sql(prompt)
        except Exception as exc:
            log.error("chat_sql_generation_error", error=str(exc))
            raw_sql = "UNANSWERABLE"

        # 4. Validate SQL query safety & schema adherence
        validated_sql = self.sql_validator.validate_sql(raw_sql, catalog)

        # 5. Execute read-only SELECT query against PostgreSQL
        result_data, row_count, execution_time_ms = self.sql_executor.execute_query(validated_sql)

        # 6. Synthesize plain English business answer from result data
        answer = self.answer_synthesizer.synthesize_answer(question, result_data, validated_sql)

        format_date = lambda d: d.strftime("%d %b %Y, %I:%M %p")
        generated_at = format_date(datetime.now(timezone.utc))

        log.info("chat_sql_processed", database=db_name, question=question[:50], row_count=row_count, execution_time_ms=execution_time_ms)

        return {
            "question": question,
            "answer": answer,
            "sql": validated_sql,
            "result_data": result_data,
            "row_count": row_count,
            "execution_time_ms": execution_time_ms,
            "generated_at": generated_at,
            "database": db_name
        }
