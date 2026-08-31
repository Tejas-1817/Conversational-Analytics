"""Answer Synthesizer.

Synthesizes concise, accurate plain English business answers directly from
user questions and query execution result data using LLM.
"""
from typing import Any, Dict, List
import structlog
from app.chat_sql.llm_provider import LLMProvider

log = structlog.get_logger(__name__)


def _format_val(val: Any) -> str:
    """Formats numeric and NULL values nicely for natural language display."""
    if val is None:
        return "0"
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

    def __init__(self, use_llm: bool = True):
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
        prompt = f"""You are an elite Senior Strategic Business Advisor and Executive Data Analyst. Your objective is to analyze the user's business question alongside the executed database query results, and translate those numbers into actionable business intelligence.

CRITICAL RESPONSE GROUNDING RULES:
1. Every numerical statement MUST be strictly traceable to the executed query result data. Never fabricate metrics, percentages, revenue figures, or growth rates.
2. Every factual business statement MUST be supported by the data. Distinguish clearly between direct FACTS (from data) and RECOMMENDATIONS (proposed actions).
3. Use consultative, advisory phrasing ("Consider...", "The data suggests...", "One potential action is...") and avoid stating guaranteed monetary returns unless mathematically proven by data.

Question: {question}
Executed SQL Query: {sql}
Query Result Data: {data_preview}

Please structure your response into the following clear markdown sections:
1. 📊 EXECUTIVE SUMMARY & METRIC BREAKDOWN:
   - Provide a direct 1-2 sentence descriptive answer stating the exact key metrics from the query result.
2. ⚡ OPERATIONAL IMPROVEMENT ADVICE:
   - Give 2 actionable recommendations on how to optimize daily operations, inventory, or workflow based strictly on these figures.
3. 📈 PRODUCT SALES & REVENUE GROWTH STRATEGIES:
   - Give 2 specific strategies to increase product sales, boost order volume, or drive revenue growth supported by the data.
4. 🎯 LONG-TERM BUSINESS GROWTH TIPS:
   - Share 1 key strategic tip for long-term scalability and business performance.
5. 💡 SUGGESTED FOLLOW-UP ANALYTICS QUESTIONS:
   - Provide 2-3 relevant, logical follow-up questions that the user can ask next to explore this data further.

Answer:
"""
        try:
            raw_answer = self.llm_provider.generate_text(prompt, max_tokens=256, timeout=120)
            return raw_answer
        except Exception as exc:
            log.warning("llm_answer_synthesis_failed_using_deterministic_fallback", error=str(exc))
            first_row = result_data[0]
            values_str = ", ".join([f"{k}: {_format_val(v)}" for k, v in first_row.items()])
            return f"The query returned {row_count} records: {values_str}."
