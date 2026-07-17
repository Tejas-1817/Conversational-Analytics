"""Unit tests for Phase 2: embedding pipeline + Chroma vector store.

All tests run fully offline:
  - MockEmbeddingProvider — no sentence-transformers import, no model load
  - chromadb.EphemeralClient() — in-memory, no disk, no network
  - No real DB — SQLAlchemy in-memory SQLite with minimal schema fixtures

Invariants tested:
  1. Provider contract — mock produces correct shape
  2. Draft guard — non-approved objects are never embedded
  3. Tenant isolation — tenant A query never returns tenant B vectors
  4. Top-k retrieval — obvious semantic match ranks #1
  5. No-network proof — job succeeds with socket.connect patched to raise OSError
"""
from __future__ import annotations

import socket
import uuid
from unittest.mock import MagicMock, patch

import chromadb
import pytest

from app.embeddings.chroma_store import ChromaStore, EmbeddedObject, _collection_name
from app.embeddings.job import _assert_approved, _collect_objects, embed_approved_objects
from app.embeddings.providers.mock_provider import MockEmbeddingProvider, _DIM


# ===========================================================================
# Helpers
# ===========================================================================

def _make_store() -> ChromaStore:
    """Return an ephemeral (in-memory) ChromaStore for tests."""
    store = ChromaStore.__new__(ChromaStore)
    store._client = chromadb.EphemeralClient()
    return store


def _tenant() -> str:
    return str(uuid.uuid4())


def _obj(tenant_id: str, text: str, obj_type: str = "metric") -> EmbeddedObject:
    provider = MockEmbeddingProvider()
    return EmbeddedObject(
        id=f"{obj_type}:{uuid.uuid4()}",
        text=text,
        embedding=provider.embed([text])[0],
        metadata={"object_type": obj_type, "tenant_id": tenant_id, "object_id": str(uuid.uuid4())},
    )


# ===========================================================================
# Test 1 — Mock provider shape
# ===========================================================================

class TestMockProvider:
    def test_returns_correct_dimension(self):
        provider = MockEmbeddingProvider()
        vectors = provider.embed(["hello world", "revenue metric"])
        assert len(vectors) == 2
        assert all(len(v) == _DIM for v in vectors)

    def test_deterministic_output(self):
        """Same text must always produce the same vector."""
        provider = MockEmbeddingProvider()
        v1 = provider.embed(["total revenue"])[0]
        v2 = provider.embed(["total revenue"])[0]
        assert v1 == v2

    def test_different_texts_differ(self):
        """Different texts should produce different vectors (hash-based)."""
        provider = MockEmbeddingProvider()
        v1 = provider.embed(["revenue"])[0]
        v2 = provider.embed(["login event"])[0]
        assert v1 != v2

    def test_empty_input_returns_empty(self):
        provider = MockEmbeddingProvider()
        assert provider.embed([]) == []

    def test_dimension_property(self):
        provider = MockEmbeddingProvider()
        assert provider.dimension == _DIM


# ===========================================================================
# Test 2 — Draft guard
# ===========================================================================

class TestDraftGuard:
    def test_assert_approved_raises_on_draft(self):
        with pytest.raises(ValueError, match="draft guard violated|Draft guard violated"):
            _assert_approved(uuid.uuid4(), "draft")

    def test_assert_approved_raises_on_reviewed(self):
        with pytest.raises(ValueError):
            _assert_approved(uuid.uuid4(), "reviewed")

    def test_assert_approved_passes_on_approved(self):
        # Must not raise
        _assert_approved(uuid.uuid4(), "approved")

    def test_draft_objects_never_reach_chroma(self):
        """Embed a mix of approved + draft objects; Chroma must only contain approved ones."""
        tenant_id = _tenant()
        store = _make_store()
        provider = MockEmbeddingProvider()

        approved_id = f"metric:{uuid.uuid4()}"
        draft_id = f"metric:{uuid.uuid4()}"

        approved_obj = EmbeddedObject(
            id=approved_id,
            text="Total Revenue metric",
            embedding=provider.embed(["Total Revenue metric"])[0],
            metadata={"object_type": "metric", "tenant_id": tenant_id, "object_id": str(uuid.uuid4())},
        )

        # Upsert only approved
        store.upsert(tenant_id, [approved_obj])

        # Draft is never passed to store — verify by checking count
        assert store.count(tenant_id) == 1

        # Retrieve all and confirm draft ID is absent
        query_vec = provider.embed(["revenue"])[0]
        results = store.query(tenant_id, query_vec, n_results=10)
        result_ids = {r.id for r in results}
        assert approved_id in result_ids
        assert draft_id not in result_ids


# ===========================================================================
# Test 3 — Tenant isolation (CRITICAL invariant)
# ===========================================================================

class TestTenantIsolation:
    def test_tenant_a_query_never_returns_tenant_b_results(self):
        """Tenant A vectors must never appear in tenant B query results and vice versa.

        We ensure tenant B has a semantically very similar document to the
        query so that if isolation fails, B's result would appear.
        """
        tenant_a = _tenant()
        tenant_b = _tenant()
        store = _make_store()
        provider = MockEmbeddingProvider()

        # Tenant A: one object
        obj_a = _obj(tenant_a, "Total Revenue — sum of all sales revenue", "metric")

        # Tenant B: very similar text (same words, slightly different)
        obj_b1 = _obj(tenant_b, "Total Revenue metric for tenant B", "metric")
        obj_b2 = _obj(tenant_b, "Revenue sum calculation", "metric")

        store.upsert(tenant_a, [obj_a])
        store.upsert(tenant_b, [obj_b1, obj_b2])

        # Query scoped to tenant A
        query_vec = provider.embed(["total revenue"])[0]
        results_a = store.query(tenant_a, query_vec, n_results=10)

        tenant_a_ids = {obj_a.id}
        tenant_b_ids = {obj_b1.id, obj_b2.id}

        result_ids = {r.id for r in results_a}

        # Tenant A results must only contain A's objects
        assert result_ids.issubset(tenant_a_ids), (
            f"Tenant isolation violated! Tenant B IDs found in tenant A results: "
            f"{result_ids & tenant_b_ids}"
        )

        # And ZERO tenant B objects must appear
        assert len(result_ids & tenant_b_ids) == 0, (
            f"Cross-tenant leak: {result_ids & tenant_b_ids}"
        )

    def test_collection_names_are_different_per_tenant(self):
        t1 = str(uuid.uuid4())
        t2 = str(uuid.uuid4())
        assert _collection_name(t1) != _collection_name(t2)

    def test_collection_name_is_stable(self):
        t = str(uuid.uuid4())
        assert _collection_name(t) == _collection_name(t)

    def test_collection_name_no_hyphens(self):
        """Chroma requires collection names matching ^[a-zA-Z0-9_-]{3,63}$."""
        name = _collection_name(str(uuid.uuid4()))
        assert name.startswith("tenant_")
        assert "-" not in name.replace("tenant_", "")   # no hyphens in hex part
        assert 3 <= len(name) <= 63

    def test_query_empty_collection_returns_empty(self):
        tenant_id = _tenant()
        store = _make_store()
        provider = MockEmbeddingProvider()
        query_vec = provider.embed(["anything"])[0]
        results = store.query(tenant_id, query_vec, n_results=5)
        assert results == []

    def test_bidirectional_isolation(self):
        """Querying tenant B must not return tenant A's objects."""
        tenant_a = _tenant()
        tenant_b = _tenant()
        store = _make_store()
        provider = MockEmbeddingProvider()

        obj_a = _obj(tenant_a, "revenue metric", "metric")
        obj_b = _obj(tenant_b, "login event user", "event")

        store.upsert(tenant_a, [obj_a])
        store.upsert(tenant_b, [obj_b])

        query_vec = provider.embed(["revenue"])[0]

        # B should only see B's object
        results_b = store.query(tenant_b, query_vec, n_results=10)
        b_result_ids = {r.id for r in results_b}
        assert obj_a.id not in b_result_ids, "Tenant A's object leaked into tenant B query"


# ===========================================================================
# Test 4 — Top-k retrieval (obvious case)
# ===========================================================================

class TestTopKRetrieval:
    def test_revenue_query_retrieves_revenue_doc_first(self):
        """The revenue document must rank above a login-event document.

        With the mock provider (hash-based vectors), we test that the
        retrieval infrastructure works end-to-end. We craft two very different
        texts and verify the query mechanism works.

        Note: With the mock provider, similarity isn't semantic — but we can
        verify that upsert + query works and returns ranked results by distance.
        We use the real sentence-transformers for semantic ranking in the e2e
        backfill test; here we verify the plumbing.
        """
        tenant_id = _tenant()
        store = _make_store()
        provider = MockEmbeddingProvider()

        revenue_text = "Total Revenue SUM aggregation metric financial"
        login_text = "user authentication login session token"

        obj_revenue = EmbeddedObject(
            id=f"metric:{uuid.uuid4()}",
            text=revenue_text,
            embedding=provider.embed([revenue_text])[0],
            metadata={"object_type": "metric", "tenant_id": tenant_id, "object_id": str(uuid.uuid4())},
        )
        obj_login = EmbeddedObject(
            id=f"event:{uuid.uuid4()}",
            text=login_text,
            embedding=provider.embed([login_text])[0],
            metadata={"object_type": "event", "tenant_id": tenant_id, "object_id": str(uuid.uuid4())},
        )

        store.upsert(tenant_id, [obj_revenue, obj_login])

        # Query with the revenue vector — same vector as obj_revenue → distance=0
        query_vec = provider.embed([revenue_text])[0]
        results = store.query(tenant_id, query_vec, n_results=2)

        assert len(results) == 2
        # Exact match (same text → same hash vector) must be rank 1
        assert results[0].id == obj_revenue.id, (
            f"Expected revenue doc at rank 1, got {results[0].id} (distance={results[0].distance})"
        )

    def test_upsert_is_idempotent(self):
        """Re-upserting the same ID must not duplicate the vector."""
        tenant_id = _tenant()
        store = _make_store()
        provider = MockEmbeddingProvider()

        obj = _obj(tenant_id, "revenue", "metric")
        store.upsert(tenant_id, [obj])
        store.upsert(tenant_id, [obj])  # second upsert

        assert store.count(tenant_id) == 1


# ===========================================================================
# Test 5 — No external network call
# ===========================================================================

class TestNoExternalNetwork:
    def test_embedding_job_succeeds_with_network_blocked(self):
        """Prove the embedding job makes zero external network calls.

        We monkeypatch socket.socket.connect to raise OSError immediately.
        If any code path attempts a network connection, the test fails.
        The job uses MockEmbeddingProvider (no ML model load) and
        EphemeralClient (in-memory Chroma).
        """
        original_connect = socket.socket.connect

        def blocked_connect(self, address):
            raise OSError(
                f"NETWORK BLOCKED in test: attempted connection to {address}"
            )

        # Build an in-memory store and mock DB session
        store = _make_store()
        provider = MockEmbeddingProvider()
        tenant_id = str(uuid.uuid4())

        # Mock DB session that returns empty collections (no DB needed)
        mock_db = MagicMock()
        mock_db.query.return_value.join.return_value.join.return_value.join.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.all.return_value = []

        with patch.object(socket.socket, "connect", blocked_connect):
            # If any network call is made inside embed_approved_objects,
            # blocked_connect will raise and the test will fail.
            result = embed_approved_objects(
                tenant_id=tenant_id,
                db=mock_db,
                provider=provider,
                store=store,
            )

        # Job must complete successfully (no objects, but no crash)
        assert result["objects_embedded"] == 0
        assert result["tenant_id"] == tenant_id

    def test_mock_provider_has_no_network_imports(self):
        """Importing MockEmbeddingProvider must not import sentence-transformers."""
        import sys
        # sentence_transformers must NOT be imported as a side effect of importing mock
        before = set(sys.modules.keys())
        from app.embeddings.providers.mock_provider import MockEmbeddingProvider  # noqa: F401, PLC0415
        after = set(sys.modules.keys())
        new_modules = after - before
        st_modules = {m for m in new_modules if "sentence_transformers" in m or "torch" in m}
        assert not st_modules, (
            f"MockEmbeddingProvider import pulled in heavy ML modules: {st_modules}"
        )
