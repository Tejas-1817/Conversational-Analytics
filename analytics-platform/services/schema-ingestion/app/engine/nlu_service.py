import json
from app.llm.provider import get_llm_provider
from app.schemas_engine import NLUIntent

class NLUService:
    @staticmethod
    def parse_intent(query: str, chat_history: str = "") -> NLUIntent:
        provider = get_llm_provider()
        
        prompt = f"""
You are an expert Data Analyst and Natural Language Understanding engine.
Your task is to parse a user's analytical question into a structured intent representation.

USER QUESTION: {query}
CONVERSATION HISTORY: {chat_history}

Instructions:
1. Identify the primary 'metric' requested (e.g. Revenue, Active Users).
2. Identify all 'dimensions' to group by (e.g. Region, Product, Platform).
3. Extract 'filters' (e.g. year = 2026 -> field: year, operator: =, value: 2026).
4. Extract 'time_granularity' (e.g. "monthly" -> month, "daily" -> day).
5. Extract 'sort_by' and 'sort_direction' if applicable.
6. Extract 'limit' if requested (e.g. "top 5" -> limit: 5).
7. Handle ambiguities. If the question is purely conversational or completely unclear, set intent="clarify" or "unknown".
"""
        prompt += """
If the user message is NOT an analytics query, the model MUST return:
{
    "intent": "unknown"
}
It must NEVER return conversational text.
It must NEVER return an empty JSON object.
It must ALWAYS return valid JSON.
"""
        
        try:
            # We rely on provider.generate_structured which handles Pydantic validation
            result = provider.generate_structured(prompt, NLUIntent)
            return result
        except Exception as e:
            # Fallback for Malformed output, ValidationError, JSONDecodeError
            return NLUIntent(intent="unknown")
