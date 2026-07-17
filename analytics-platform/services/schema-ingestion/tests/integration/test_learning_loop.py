import uuid
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.db import get_session
from app.api.deps import get_current_user
from app.models import User, Conversation, ConversationMessage, ApprovedSQLExample
from app.embeddings.chroma_store import ChromaStore
from app.embeddings.feedback_job import embed_approved_examples
from app.engine.retrieval_service import RetrievalService

dummy_tenant_id = uuid.uuid4()
dummy_user_id = uuid.uuid4()
conv_id = uuid.uuid4()
q_msg_id = uuid.uuid4()
a_msg_id = uuid.uuid4()

def override_get_current_user():
    return User(id=dummy_user_id, tenant_id=dummy_tenant_id, email="test@example.com")

app.dependency_overrides[get_current_user] = override_get_current_user

class DummyProvider:
    def embed(self, texts):
        return [[0.1] * 384 for _ in texts]

def test_full_learning_loop(monkeypatch):
    mock_db = MagicMock()
    app.dependency_overrides[get_session] = lambda: mock_db
    monkeypatch.setattr("app.embeddings.registry.get_embedding_provider", lambda: DummyProvider())

    client = TestClient(app)

    from datetime import datetime, timedelta
    now = datetime.now()
    # Mock DB returns for feedback endpoint
    conv_mock = Conversation(id=conv_id, tenant_id=dummy_tenant_id)
    q_msg_mock = ConversationMessage(
        id=q_msg_id,
        conversation_id=conv_id,
        role="user",
        content="How many users joined last week?",
        created_at=now - timedelta(minutes=1)
    )
    a_msg_mock = ConversationMessage(
        id=a_msg_id,
        conversation_id=conv_id,
        role="assistant",
        content="Here is the data for users who joined last week.",
        generated_sql="SELECT count(1) FROM users WHERE created_at >= date_trunc('week', now() - interval '1 week')",
        created_at=now
    )
    mock_db.scalar.side_effect = [conv_mock, a_msg_mock]
    
    added_example = None
    from datetime import datetime
    def mock_add(obj):
        nonlocal added_example
        if isinstance(obj, ApprovedSQLExample):
            added_example = obj
            obj.id = uuid.uuid4()
            obj.question = q_msg_mock.content
            obj.generated_sql = a_msg_mock.generated_sql
            obj.created_at = datetime.now()
        else:
            obj.id = uuid.uuid4()
            obj.created_at = datetime.now()
    
    mock_db.add.side_effect = mock_add
    mock_db.refresh = MagicMock()

    # 1. Give feedback
    feedback_payload = {
        "is_positive": True,
        "correction": "This is great!"
    }
    fb_response = client.post(
        f"/engine/conversations/{conv_id}/messages/{str(a_msg_id)}/feedback",
        json=feedback_payload
    )
    assert fb_response.status_code == 200
    assert fb_response.json()["is_positive"] is True

    # Reset mock and set up for approve endpoint
    mock_db.scalar.side_effect = [a_msg_mock, q_msg_mock]


    # 2. Approve as an example
    approve_payload = {
        "message_id": str(a_msg_id)
    }
    approve_response = client.post("/engine/examples/approve", json=approve_payload)
    assert approve_response.status_code == 200
    example_data = approve_response.json()
    assert example_data["question"] == "How many users joined last week?"
    assert example_data["tenant_id"] == str(dummy_tenant_id)
    
    assert added_example is not None
    assert added_example.question == "How many users joined last week?"

    # 3. Run the embedding refresh job
    # Mock db.query for embed_approved_examples
    mock_db.query.return_value.filter.return_value.all.return_value = [added_example]
    
    store = ChromaStore(ephemeral=True)
    job_result = embed_approved_examples(dummy_tenant_id, mock_db, provider=DummyProvider(), store=store)
    assert job_result["objects_embedded"] == 1
    assert job_result["object_types"]["approved_example"] == 1

    # 4. Confirm it appears in Retrieval results for a genuine paraphrase
    paraphrased_query = "What's the total number of new signups we got over the previous week?"
    
    # Mock db.scalars for RetrievalService.retrieve bulk hydration
    mock_db.scalars.return_value.all.return_value = [added_example]

    hits = RetrievalService.retrieve(
        query_text=paraphrased_query,
        tenant_id=dummy_tenant_id,
        db=mock_db,
        store=store
    )

    assert hits.used_rag is True
    assert len(hits.approved_examples) > 0
    assert hits.approved_examples[0][0].question == "How many users joined last week?"
    assert hits.approved_examples[0][0].generated_sql == "SELECT count(1) FROM users WHERE created_at >= date_trunc('week', now() - interval '1 week')"
