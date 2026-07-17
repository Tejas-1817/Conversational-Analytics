import sys
import os
import socket

# Adjust path so we can import from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import get_settings
from app.llm.orchestrator import ai_orchestrator
from app.schemas_engine import RouterResult

def run_test():
    # Force settings
    settings = get_settings()
    settings.llm_provider = "ollama"

    print(f"Running direct orchestrator test with llm_provider={settings.llm_provider}")
    
    try:
        res = ai_orchestrator.generate_structured("query: hello", RouterResult)
        print("SUCCESS:")
        print(res)
    except Exception as e:
        print(f"FAILED with {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
