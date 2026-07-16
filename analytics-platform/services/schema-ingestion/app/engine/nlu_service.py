from app.llm.orchestrator import ai_orchestrator
from app.schemas_engine import NLUIntent
from app.engine.context_manager import ConversationContext
import json

class NLUService:
    @staticmethod
    def parse_intent(query: str, context: ConversationContext) -> NLUIntent:
        prompt = f"""
You are an expert Data Analyst and Natural Language Understanding engine.
Your task is to parse a user's analytical question into a structured intent representation.
You MUST properly handle follow-up questions by inheriting metrics, dimensions, and filters from the previous query if the user does not explicitly change them.

USER QUESTION: {query}

--- CONVERSATION CONTEXT ---
CHAT HISTORY:
{context.chat_history}

PREVIOUS INTENT:
{json.dumps(context.last_intent, indent=2) if context.last_intent else "None"}
----------------------------

Instructions:
1. Identify the primary 'metric' or 'kpi'. If the user asks a follow-up (e.g. "What about by region?"), inherit the metric from PREVIOUS INTENT.
2. Identify all 'dimensions' to group by. If follow-up, merge or replace based on user phrasing (e.g. "by product instead" replaces; "and by region" adds).
3. Extract 'filters'. Merge with previous filters unless the user explicitly removes them (e.g. "for all regions").
4. Extract 'time_granularity' (e.g. "monthly", "daily").
5. Extract 'time_intelligence' (e.g. "YTD", "last year").
6. Handle ambiguities. If completely unclear, set intent="clarify" or "unknown".
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
            result = ai_orchestrator.generate_structured(prompt, NLUIntent)
            return result
        except Exception:
            # Fallback for Malformed output, ValidationError, JSONDecodeError
            return NLUIntent(intent="unknown")
