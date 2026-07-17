"""Tenant-isolated Chroma vector store wrapper.

Invariants enforced here:
  1. One Chroma collection per tenant — collection name encodes the tenant ID.
  2. Every query ALWAYS passes where={"tenant_id": <str>} — cross-tenant leakage
     is impossible even if the collection name check is bypassed.
  3. This module never touches the metadata DB — it is purely a vector-store
     abstraction layer.

Usage:
    store = ChromaStore()                          # persistent (prod)
    store = ChromaStore(ephemeral=True)            # in-memory (tests)

    store.upsert(tenant_id, objects)
    results = store.query(tenant_id, "revenue", n_results=5)
    store.delete(tenant_id, object_id)
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import chromadb
from chromadb import Collection

from app.config import get_settings


# ---------------------------------------------------------------------------
# Data transfer objects
# ---------------------------------------------------------------------------

@dataclass
class EmbeddedObject:
    """An object ready to be stored in the vector store."""
    id: str                       # str(uuid) — stable across upserts
    text: str                     # the text that was embedded
    embedding: list[float]        # pre-computed vector
    metadata: dict = field(default_factory=dict)  # object_type, tenant_id, …


@dataclass
class RetrievalResult:
    """A single hit returned by ChromaStore.query()."""
    id: str
    text: str
    metadata: dict
    distance: float


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

def _collection_name(tenant_id: str | uuid.UUID) -> str:
    """Stable, Chroma-safe collection name for a tenant.

    Chroma collection names must match ^[a-zA-Z0-9_-]{3,63}$.
    We use 'tenant_' + the UUID in lowercase hex (no hyphens).
    """
    hex_id = str(tenant_id).replace("-", "").lower()
    return f"tenant_{hex_id}"


class ChromaStore:
    """Thread-safe wrapper around a Chroma client with per-tenant collections."""

    def __init__(self, ephemeral: bool = False) -> None:
        if ephemeral:
            self._client = chromadb.EphemeralClient()
        else:
            persist_dir = get_settings().chroma_persist_dir
            self._client = chromadb.PersistentClient(path=persist_dir)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_collection(self, tenant_id: str | uuid.UUID) -> Collection:
        name = _collection_name(tenant_id)
        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upsert(self, tenant_id: str | uuid.UUID, objects: list[EmbeddedObject]) -> int:
        """Upsert a batch of embedded objects into the tenant's collection.

        Returns the number of objects upserted.
        The metadata dict on each object MUST contain 'tenant_id' — this is
        enforced here so that the query-side where-filter always has a value.
        """
        if not objects:
            return 0

        collection = self._get_or_create_collection(tenant_id)
        tenant_str = str(tenant_id)

        ids: list[str] = []
        embeddings: list[list[float]] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        for obj in objects:
            # Enforce tenant_id presence in metadata — invariant
            meta = dict(obj.metadata)
            meta["tenant_id"] = tenant_str  # always overwrite to be safe
            ids.append(obj.id)
            embeddings.append(obj.embedding)
            documents.append(obj.text)
            metadatas.append(meta)

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        return len(ids)

    def query(
        self,
        tenant_id: str | uuid.UUID,
        query_embedding: list[float],
        n_results: int = 5,
    ) -> list[RetrievalResult]:
        """Query the tenant's collection.

        The where filter on tenant_id is NON-NEGOTIABLE — it is always applied
        regardless of which collection is opened, so a misconfigured collection
        name cannot leak cross-tenant data.
        """
        collection = self._get_or_create_collection(tenant_id)
        tenant_str = str(tenant_id)

        # Guard: if collection is empty Chroma raises
        count = collection.count()
        if count == 0:
            return []

        actual_n = min(n_results, count)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=actual_n,
            where={"tenant_id": tenant_str},   # INVARIANT: always filter by tenant
            include=["documents", "metadatas", "distances"],
        )

        hits: list[RetrievalResult] = []
        for i, doc_id in enumerate(results["ids"][0]):
            hits.append(RetrievalResult(
                id=doc_id,
                text=results["documents"][0][i],
                metadata=results["metadatas"][0][i],
                distance=results["distances"][0][i],
            ))
        return hits

    def delete(self, tenant_id: str | uuid.UUID, object_id: str) -> None:
        """Remove a single vector by its object ID."""
        collection = self._get_or_create_collection(tenant_id)
        collection.delete(ids=[object_id])

    def count(self, tenant_id: str | uuid.UUID) -> int:
        """Return the number of vectors in the tenant's collection."""
        collection = self._get_or_create_collection(tenant_id)
        return collection.count()
