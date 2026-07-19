import json
from fastapi.testclient import TestClient
from app.main import app
from app.db import session_scope
from app.models import User, Conversation

client = TestClient(app)

def test_query():
    with session_scope() as db:
        user = db.query(User).first()
        if not user:
            print("No users in DB")
            return
            
        # Create a new conversation
        response = client.post(
            "/engine/conversations", 
            json={"title": "Test Conversation"},
            headers={"Authorization": f"Bearer {user.id}"} # assuming some auth mock or we can override dependency
        )
        # Actually the app uses Depends(get_current_user)
        # Let's override it
        from app.api.deps import get_current_user
        app.dependency_overrides[get_current_user] = lambda: user
        
        response = client.post("/engine/conversations", json={"title": "Test Conversation"})
        if response.status_code != 200:
            print("Failed to create conversation:", response.json())
            return
            
        conv_id = response.json()["id"]
        print(f"Conversation created: {conv_id}")
        
        # Send query
        response = client.post(
            f"/engine/conversations/{conv_id}/query",
            json={"message": "Show total revenue by region"}
        )
        print("Response:", json.dumps(response.json(), indent=2))

if __name__ == "__main__":
    test_query()
