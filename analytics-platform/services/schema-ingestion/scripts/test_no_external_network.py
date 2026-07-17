import sys
import os
import socket
from unittest.mock import patch

# Force environment variable BEFORE importing app code
os.environ["LLM_PROVIDER"] = "ollama"

# Adjust path so we can import from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.api.engine import ask_question, create_conversation
from app.schemas_engine import ChatRequest
from app.db import session_scope
from app.models import User
from app.config import get_settings
from app.engine.context_manager import ConversationContext

def block_outbound_sockets():
    """
    Monkeypatches socket.socket.connect to raise an exception for any connection
    that is not to 127.0.0.1 or localhost.
    """
    original_connect = socket.socket.connect

    def mock_connect(self, address):
        host = address[0]
        port = address[1]
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise ConnectionRefusedError(
                f"NETWORK EGRESS BLOCKED: Attempted to connect to {host}:{port}"
            )
        return original_connect(self, address)

    return patch("socket.socket.connect", new=mock_connect)


def run_test():
    from app.llm.orchestrator import ai_orchestrator
    print(f"Running offline network test with ai_orchestrator using {ai_orchestrator.provider.__class__.__name__}")
    
    with block_outbound_sockets():
        with session_scope() as db:
            # Get admin user
            user = db.query(User).filter_by(role="ADMIN").first()
            if not user:
                print("No admin user found. Please run seed script first.")
                return

            # Create a conversation
            conv = create_conversation(db=db, user=user)

            print("Blocked all outbound sockets (except localhost).")
            print("Executing 'ask_question' with query 'Show total revenue by region'...")
            
            req = ChatRequest(message="Show total revenue by region")
            
            try:
                response = ask_question(
                    conv_id=conv.id,
                    req=req,
                    db=db,
                    user=user
                )
                print("\nSUCCESS! Chat flow completed completely offline.")
                print("SQL Generated:")
                print(response.generated_sql)
                print("Data Sample:")
                print(response.result_data)
            except Exception as e:
                print(f"\nFAILED: {e}")
                raise


if __name__ == "__main__":
    run_test()
