import os
import sys
import uuid
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from app.db import get_engine, get_session
from app.models import Tenant, User, Conversation
from app.schemas_engine import ChatRequest
from app.api.engine import ask_question, create_conversation
from app.security.auth import get_password_hash
from sqlalchemy.orm import Session
from sqlalchemy import text

def mock_generate_structured(prompt, schema):
    from app.schemas_engine import RouterResult, NLUIntent
    if schema == RouterResult:
        user_message_line = [line for line in prompt.split('\n') if line.startswith('USER MESSAGE:')]
        if user_message_line:
            q_lower = user_message_line[0].replace('USER MESSAGE:', '').strip().lower()
        else:
            q_lower = prompt.lower()
        
        if "asdfqwerzxcv" in q_lower or "garbage" in q_lower:
            return RouterResult(route="unknown", confidence=0.0, reason="test")
        elif q_lower in ["hi", "hello", "hiiii"]:
            return RouterResult(route="greeting", confidence=0.99, reason="test")
        elif q_lower in ["how are you?", "who are you?", "thanks", "goodbye", ":)"]:
            return RouterResult(route="conversation", confidence=0.99, reason="test")
        elif q_lower in ["help", "what can you do?"]:
            return RouterResult(route="help", confidence=0.99, reason="test")
        else:
            return RouterResult(route="analytics", confidence=0.99, reason="test")
    elif schema == NLUIntent:
        if "asdf" in prompt.lower():
            raise Exception("Malformed NLU Output")
        return NLUIntent(intent="aggregate", metric="Revenue")
    return None

import unittest.mock
@unittest.mock.patch("app.engine.router_service.get_llm_provider")
@unittest.mock.patch("app.engine.nlu_service.get_llm_provider")
def test_queries(mock_nlu_provider, mock_router_provider):
    mock_provider_instance = unittest.mock.MagicMock()
    mock_provider_instance.generate_structured.side_effect = mock_generate_structured
    mock_provider_instance.generate_text.return_value = "Hello! How can I help you today?"
    mock_router_provider.return_value = mock_provider_instance
    mock_nlu_provider.return_value = mock_provider_instance
    
    print("\n--- Verifying Intelligent Intent Router ---\n")
    
    # 1. Setup minimal db context
    engine = get_engine()
    with engine.connect() as conn:
        tenant_id = conn.execute(text("SELECT id FROM tenants LIMIT 1")).scalar()
        if not tenant_id:
            tenant_id = uuid.uuid4()
            conn.execute(text(f"INSERT INTO tenants (id, name) VALUES ('{tenant_id}', 'Router Test Tenant')"))
        
        user_id = conn.execute(text(f"SELECT id FROM users WHERE tenant_id = '{tenant_id}' LIMIT 1")).scalar()
        if not user_id:
            user_id = uuid.uuid4()
            conn.execute(text(f"INSERT INTO users (id, tenant_id, email, password_hash) VALUES ('{user_id}', '{tenant_id}', 'router_test@example.com', 'hash')"))
        conn.commit()

    # Create dummy User object
    user = User(id=user_id, tenant_id=tenant_id, email="router_test@example.com", role="admin")
    db = next(get_session())
    
    # Create conversation
    conv = create_conversation(db, user)
    
    queries = [
        ("Hi", "greeting"),
        ("Hello", "greeting"),
        ("Hiiii", "greeting"),
        ("How are you?", "conversation"),
        ("Who are you?", "conversation"),
        ("Help", "help"),
        ("What can you do?", "help"),
        ("Show revenue", "analytics"),
        ("Revenue by region", "analytics"),
        ("Top 10 customers", "analytics"),
        ("Thanks", "conversation"),
        ("Goodbye", "conversation"),
        (":)", "conversation"),
        ("asdfqwerzxcv", "unknown")
    ]
    
    passed = 0
    
    for q, expected_route in queries:
        print(f"Testing: '{q}' (Expected: {expected_route})")
        req = ChatRequest(message=q)
        try:
            resp = ask_question(conv.id, req, db, user)
            actual_route = resp.route
            print(f"  -> Actual Route: {actual_route}")
            print(f"  -> Answer: {resp.content[:100]}...")
            if actual_route == expected_route:
                print("  [PASS]")
                passed += 1
            else:
                print("  [FAIL]")
        except Exception as e:
            print(f"  [ERROR] {str(e)}")
            
    print(f"\nResults: {passed} / {len(queries)} passed.")
    
    # Testing robust NLU (bypassing router manually to simulate analytics error)
    print("\nTesting Malformed NLU Fallback (Sending garbage directly to NLU)...")
    from app.engine.nlu_service import NLUService
    result = NLUService.parse_intent("asdfasdf")
    print(f"  -> Fallback Intent: {result.intent}")
    if result.intent == "unknown":
        print("  [PASS] NLU safely fell back to 'unknown'")
    else:
        print("  [FAIL] NLU did not fall back safely")

if __name__ == "__main__":
    test_queries()
