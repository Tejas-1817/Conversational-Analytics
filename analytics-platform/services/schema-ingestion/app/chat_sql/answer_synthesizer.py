"""Answer Synthesizer.

Synthesizes concise, accurate plain English business answers directly from
user questions and query execution result data using LLM.
"""
from typing import Any, Dict, List
import structlog
from app.chat_sql.llm_provider import LLMProvider

log = structlog.get_logger(__name__)


def _format_val(val: Any) -> str:
    """Formats numeric values nicely for natural language display."""
    if isinstance(val, (int, float)):
        return f"{val:,}" if isinstance(val, int) else f"{val:,.2f}"
    try:
        from decimal import Decimal
        if isinstance(val, Decimal):
            return f"{float(val):,.2f}"
    except Exception:
        pass
    return str(val)


class AnswerSynthesizer:
    """Synthesizes natural language business answers from DB result data instantly without SQL validation."""

    def __init__(self, use_llm: bool = False):
        self.use_llm = use_llm
        self.llm_provider = LLMProvider()

    def synthesize_answer(self, question: str, result_data: List[Dict[str, Any]], sql: str) -> str:
        """Synthesizes a direct, concise 1-2 sentence plain English answer from data."""
        if not result_data:
            if "UNANSWERABLE" in sql.upper() or "CANNOT GENERATE" in sql.upper():
                return "I cannot generate a SQL query because the required tables or columns do not exist in the connected database schema."
            return "No matching data records were found in the connected database for this query."

        row_count = len(result_data)
        cols = list(result_data[0].keys()) if row_count > 0 and isinstance(result_data[0], dict) else []

        # 1. Deterministic Fast Synthesis (0ms Latency)
        if not self.use_llm:
            # Case A: 1 Row + 1 Column (Single Scalar Metric)
            if row_count == 1 and len(cols) == 1:
                val = result_data[0][cols[0]]
                metric_name = cols[0].replace("_", " ").title()
                
                # Context-aware phrasing based on question
                q_lower = question.lower()
                if "active" in q_lower and "customer" in q_lower:
                    return f"There are {_format_val(val)} active customers currently in the system."
                elif "count" in q_lower or "how many" in q_lower:
                    return f"The total count for {metric_name} is {_format_val(val)}."
                return f"The total {metric_name} is {_format_val(val)}."

            # Case B: 1 Row + Multiple Columns (Entity Detail)
            if row_count == 1 and len(cols) > 1:
                rec = result_data[0]
                first_val = _format_val(rec[cols[0]])
                details = ", ".join([f"{c.replace('_', ' ').title()}: {_format_val(rec[c])}" for c in cols[1:]])
                return f"Highest record: {first_val} ({details})."

            # Case C: Multiple Rows (Categorical / Time-Series)
            if row_count > 1:
                top_row = result_data[0]
                first_col = cols[0]
                second_col = cols[1] if len(cols) > 1 else cols[0]
                top_label = str(top_row.get(first_col, ""))
                top_val = _format_val(top_row.get(second_col, ""))

                return f"Retrieved {row_count} records. Top item is '{top_label}' with {second_col.replace('_', ' ')} of {top_val}."

        # 2. LLM Text Synthesis (Uses generate_text WITHOUT SQL validation)
        data_preview = str(result_data[:5])
        prompt = f"""Synthesize a direct, concise 1-2 sentence plain English business answer from the data below.

Question: {question}
SQL Query: {sql}
Result Data: {data_preview}

CRITICAL RULES:
1. Provide a direct 1-2 sentence business answer in plain English.
2. State exact numbers from the Result Data.
3. Do NOT explain SQL logic or code.

Answer:
"""
        try:
            raw_answer = self.llm_provider.generate_text(prompt, max_tokens=128, timeout=15)
            return raw_answer
        except Exception as exc:
            log.warning("llm_answer_synthesis_failed_using_deterministic_fallback", error=str(exc))
            first_row = result_data[0]
            values_str = ", ".join([f"{k}: {_format_val(v)}" for k, v in first_row.items()])
            return f"The query returned {row_count} records: {values_str}."
