import sys
import os

# Adjust path so we can import from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import get_settings
from app.llm.orchestrator import ai_orchestrator
from app.schemas_engine import RouterResult

def run_test():
    settings = get_settings()
    settings.llm_provider = "ollama"

    print("Running orchestrator test for 'Show total revenue by region'")
    prompt = """
You are an intelligent Intent Router for an Analytics AI Assistant.
Your job is to classify the user's message into one of the following routes:
1. "analytics": The user is asking a data question, looking for metrics, trends, or charts (e.g. "Show revenue", "Top 10 customers").
2. "greeting": The user is simply saying hello or greeting you (e.g. "Hi", "Hello", "Good morning", "Hiiii").
3. "help": The user is asking for help, what you can do, or instructions (e.g. "Help", "What can you do?", "How do I use this?").
4. "conversation": The user is engaging in general chat, small talk, expressing thanks, or asking non-analytics questions (e.g. "How are you?", "Who are you?", "Thanks", "Goodbye").
5. "unknown": If you are completely unsure or it is garbage text.

USER MESSAGE: Show total revenue by region

Return a JSON object matching the RouterResult schema with 'route', 'confidence' (0.0-1.0), and 'reason'.
"""
    raw_response = ai_orchestrator.provider.generate_structured_json(prompt, RouterResult)
    print("RAW RESPONSE FROM OLLAMA:")
    print(repr(raw_response))

    try:
        parsed = RouterResult.model_validate_json(raw_response)
        print("PARSED:", parsed)
    except Exception as e:
        print("VALIDATION ERROR:", e)

if __name__ == "__main__":
    run_test()
