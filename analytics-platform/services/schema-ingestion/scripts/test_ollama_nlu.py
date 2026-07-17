import sys
import os

# Adjust path so we can import from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import get_settings
from app.llm.orchestrator import ai_orchestrator
from app.schemas_engine import RouterResult, NLUIntent
from app.engine.context_manager import ConversationContext
import json

def run_test():
    settings = get_settings()
    settings.llm_provider = "ollama"

    print("Running orchestrator test for 'Show total revenue by region' - NLU Intent parsing")
    
    query = "Show total revenue by region"
    context = ConversationContext(chat_history=[], last_intent=None, last_plan=None)
    
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

    raw_response = ai_orchestrator.provider.generate_structured_json(prompt, NLUIntent)
    print("RAW RESPONSE FROM OLLAMA:")
    print(repr(raw_response))

    try:
        parsed = NLUIntent.model_validate_json(raw_response)
        print("PARSED:", parsed)
    except Exception as e:
        print("VALIDATION ERROR:", e)

if __name__ == "__main__":
    run_test()
