"""Answer Synthesizer.

Synthesizes concise, accurate plain English business answers directly from
user questions and query execution result data using LLM.
"""
from typing import Any, Dict, List
import structlog
from app.chat_sql.llm_provider import LLMProvider

log = structlog.get_logger(__name__)


class AnswerSynthesizer:
    """Synthesizes natural language business answers from DB result data."""

    def __init__(self):
        self.llm_provider = LLMProvider()

    def synthesize_answer(self, question: str, result_data: List[Dict[str, Any]], sql: str) -> str:
        """Synthesizes a 1-2 sentence plain English answer from data."""
        if not result_data:
            if "UNANSWERABLE" in sql.upper() or "CANNOT GENERATE" in sql.upper():
                return "I cannot generate a SQL query because the required tables or columns do not exist in the connected database schema."
            return "No matching data records were found in the connected database for this query."

        # Truncate result data preview if large
        data_preview = str(result_data[:5])
        prompt = f"""You are an expert data analyst synthesizing a clear, accurate, 1-2 sentence plain English business answer.

Question: {question}
SQL Query: {sql}
Result Data: {data_preview}

CRITICAL RULES:
1. Provide a direct, concise 1-2 sentence business answer in plain English.
2. State exact numbers and figures from the Result Data.
3. Do NOT explain SQL logic or technical syntax.
4. Return raw text answer ONLY.

Answer:
"""
        try:
            raw_answer = self.llm_provider.generate_sql(prompt)
            # Remove any trailing brackets or quotes if present
            cleaned_answer = raw_answer.strip().strip('"')
            return cleaned_answer
        except Exception as exc:
            log.error("answer_synthesis_failed", error=str(exc))
            # Fallback to direct string representation of first row if LLM synthesis fails
            first_row = result_data[0]
            values_str = ", ".join([f"{k}: {v}" for k, v in first_row.items()])
            return f"The database query returned: {values_str}."
