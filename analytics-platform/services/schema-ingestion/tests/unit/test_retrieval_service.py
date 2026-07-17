import uuid

from app.engine.retrieval_service import RetrievalService
from app.embeddings.chroma_store import RetrievalResult
from app.config import get_settings


class DummyProvider:
    def embed(self, texts):
        return [[0.1] * 384]


class DummyChromaStore:
    def __init__(self, raw_results):
        self.raw_results = raw_results

    def query(self, tenant_id, query_embedding, n_results):
        return self.raw_results


def test_retrieve_returns_hits_above_threshold(monkeypatch):
    monkeypatch.setattr("app.embeddings.registry.get_embedding_provider", lambda: DummyProvider())

    raw = [
        RetrievalResult(
            id="1",
            text="doc",
            metadata={"object_id": str(uuid.uuid4()), "object_type": "metric"},
            distance=0.3
        )
    ]
    store = DummyChromaStore(raw_results=raw)

    hits = RetrievalService.retrieve(
        query_text="test",
        tenant_id=uuid.uuid4(),
        db=None,
        store=store
    )

    assert hits.used_rag is True
    assert len(hits.raw_results) == 1
    assert hits.raw_results[0].distance == 0.3


def test_retrieve_falls_back_when_chroma_empty(monkeypatch):
    monkeypatch.setattr("app.embeddings.registry.get_embedding_provider", lambda: DummyProvider())
    store = DummyChromaStore(raw_results=[])

    hits = RetrievalService.retrieve(
        query_text="test",
        tenant_id=uuid.uuid4(),
        db=None,
        store=store
    )

    assert hits.used_rag is False
    assert len(hits.raw_results) == 0


def test_retrieve_discards_below_threshold(monkeypatch):
    monkeypatch.setattr("app.embeddings.registry.get_embedding_provider", lambda: DummyProvider())

    settings = get_settings()
    settings.rag_distance_threshold = 0.5

    raw = [
        RetrievalResult(
            id="1",
            text="doc",
            metadata={"object_id": str(uuid.uuid4()), "object_type": "metric"},
            distance=0.6  # Worse than threshold
        )
    ]
    store = DummyChromaStore(raw_results=raw)

    hits = RetrievalService.retrieve(
        query_text="test",
        tenant_id=uuid.uuid4(),
        db=None,
        store=store
    )

    assert hits.used_rag is False
    assert len(hits.raw_results) == 0


def test_retrieve_disabled_by_config():
    settings = get_settings()
    settings.rag_enabled = False

    hits = RetrievalService.retrieve(
        query_text="test",
        tenant_id=uuid.uuid4(),
        db=None,
        store=None
    )

    assert hits.used_rag is False
    settings.rag_enabled = True  # reset
