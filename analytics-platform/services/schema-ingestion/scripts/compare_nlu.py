import os
import sys

# Adjust path so we can import from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import get_settings
from app.engine.nlu_service import NLUService
from app.engine.context_manager import ConversationContext
from scripts.golden_eval import QUESTIONS

def test_model(provider: str):
    print(f"\n{'='*50}\nTESTING LLM PROVIDER: {provider.upper()}\n{'='*50}")
    
    # Set the provider in the environment so get_settings() picks it up, or just monkeypatch get_settings
    settings = get_settings()
    settings.llm_provider = provider
    
    # We must reset the AI orchestrator's provider since it's initialized globally
    from app.llm.orchestrator import AIOrchestrator
    orchestrator = AIOrchestrator() # Creates a new one with the current settings

    # Let's monkeypatch the global ai_orchestrator so NLUService uses it
    import app.engine.nlu_service
    app.engine.nlu_service.ai_orchestrator = orchestrator

    context = ConversationContext(chat_history=[], last_intent=None, last_plan=None)
    
    for idx, (question, _, _) in enumerate(QUESTIONS, 1):
        print(f"\nQ{idx}: {question}")
        try:
            intent = app.engine.nlu_service.NLUService.parse_intent(question, context)
            print("  ->", intent.model_dump_json(exclude_none=True))
        except Exception as e:
            print("  -> ERROR:", str(e))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_model(sys.argv[1])
    else:
        test_model("ollama")
        test_model("gemini")
