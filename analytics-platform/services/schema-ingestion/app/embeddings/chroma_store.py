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

import math
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog
from app.config import get_settings

try:
    import chromadb
    from chromadb import Collection
    HAVE_CHROMADB = True
except Exception as exc:
    chromadb = None
    Collection = Any  # type: ignore
    HAVE_CHROMADB = False

log = structlog.get_logger(__name__)


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


def _cosine_distance(v1: list[float], v2: list[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 1.0
    sim = max(-1.0, min(1.0, dot / (norm1 * norm2)))
    return 1.0 - sim


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

def _collection_name(tenant_id: str | uuid.UUID, source_id: str | uuid.UUID | None = None) -> str:
    """Stable, Chroma-safe collection name for a tenant and optional data source.

    Chroma collection names must match ^[a-zA-Z0-9_-]{3,63}$.
    We format as 'tenant_' + tenant_hex + optional '_src_' + source_hex.
    """
    hex_tenant = str(tenant_id).replace("-", "").lower()
    if source_id:
        hex_source = str(source_id).replace("-", "").lower()
        return f"tenant_{hex_tenant[:16]}_src_{hex_source[:16]}"
    return f"tenant_{hex_tenant}"


class ChromaStore:
    """Thread-safe wrapper around a Chroma client with per-tenant and per-source collections."""

    def __init__(self, ephemeral: bool = False) -> None:
        settings = get_settings()
        self._fallback_store: dict[str, dict[str, dict[str, Any]]] = {}

        if not HAVE_CHROMADB:
            log.warning("chromadb_unavailable_using_in_memory_fallback")
            self._client = None
            return

        if ephemeral or settings.chroma_mode == "ephemeral":
            self._client = chromadb.EphemeralClient()
        elif settings.chroma_mode == "cloud":
            if not settings.chroma_api_key:
                raise RuntimeError("CHROMA_API_KEY is required in cloud mode")
            if not settings.chroma_tenant:
                raise RuntimeError("CHROMA_TENANT is required in cloud mode")
            if not settings.chroma_database:
                raise RuntimeError("CHROMA_DATABASE is required in cloud mode")

            try:
                self._client = chromadb.CloudClient(
                    tenant=settings.chroma_tenant,
                    database=settings.chroma_database,
                    api_key=settings.chroma_api_key,
                    cloud_host=settings.chroma_host,
                )
                self._client.heartbeat()
                log.info(
                    "chroma_store_cloud_client_initialized",
                    tenant=settings.chroma_tenant,
                    database=settings.chroma_database,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Could not connect to Chroma Cloud: {exc}"
                ) from exc 
        else:
            try:
                self._client = chromadb.PersistentClient(
                    path=settings.chroma_persist_dir
                )
            except Exception as exc:
                log.warning("chromadb_persistent_client_failed_fallback_to_ephemeral", error=str(exc))
                self._client = chromadb.EphemeralClient()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_collection(
        self,
        tenant_id: str | uuid.UUID,
        source_id: str | uuid.UUID | None = None
    ) -> Collection | None:
        if self._client is None:
            return None
        name = _collection_name(tenant_id, source_id=source_id)
        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upsert(
        self,
        tenant_id: str | uuid.UUID,
        objects: list[EmbeddedObject],
        source_id: str | uuid.UUID | None = None
    ) -> int:
        """Upsert a batch of embedded objects into the tenant's/source's collection."""
        if not objects:
            return 0

        tenant_str = str(tenant_id)
        col_name = _collection_name(tenant_id, source_id=source_id)

        if self._client is None:
            if col_name not in self._fallback_store:
                self._fallback_store[col_name] = {}
            for obj in objects:
                meta = dict(obj.metadata)
                meta["tenant_id"] = tenant_str
                if source_id:
                    meta["source_id"] = str(source_id)
                self._fallback_store[col_name][obj.id] = {
                    "id": obj.id,
                    "text": obj.text,
                    "embedding": obj.embedding,
                    "metadata": meta,
                }
            return len(objects)

        collection = self._get_or_create_collection(tenant_id, source_id=source_id)
        ids: list[str] = []
        embeddings: list[list[float]] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        for obj in objects:
            meta = dict(obj.metadata)
            meta["tenant_id"] = tenant_str  # invariant
            if source_id:
                meta["source_id"] = str(source_id)
            ids.append(obj.id)
            embeddings.append(obj.embedding)
            documents.append(obj.text)
            metadatas.append(meta)

        BATCH_SIZE = 100
        for i in range(0, len(ids), BATCH_SIZE):
            collection.upsert(
                ids=ids[i : i + BATCH_SIZE],
                embeddings=embeddings[i : i + BATCH_SIZE],
                documents=documents[i : i + BATCH_SIZE],
                metadatas=metadatas[i : i + BATCH_SIZE],
            )
        return len(ids)

    def query(
        self,
        tenant_id: str | uuid.UUID,
        query_embedding: list[float],
        n_results: int = 5,
        source_id: str | uuid.UUID | None = None,
        object_types: list[str] | None = None,
    ) -> list[RetrievalResult]:
        """Query the tenant's/source's collection."""
        tenant_str = str(tenant_id)
        col_name = _collection_name(tenant_id, source_id=source_id)

        if self._client is None:
            col_data = self._fallback_store.get(col_name, {})
            if not col_data:
                return []
            candidates = []
            for item in col_data.values():
                meta = item["metadata"]
                if meta.get("tenant_id") != tenant_str:
                    continue
                if source_id is not None and meta.get("source_id") != str(source_id):
                    continue
                if object_types and meta.get("object_type") not in object_types:
                    continue
                dist = _cosine_distance(query_embedding, item["embedding"])
                candidates.append((dist, item))

            candidates.sort(key=lambda x: x[0])
            hits = []
            for dist, item in candidates[:n_results]:
                hits.append(RetrievalResult(
                    id=item["id"],
                    text=item["text"],
                    metadata=item["metadata"],
                    distance=dist,
                ))
            return hits

        collection = self._get_or_create_collection(tenant_id, source_id=source_id)
        count = collection.count()
        if count == 0:
            return []

        actual_n = min(n_results, count)

        filters: list[dict] = [
            {"tenant_id": tenant_str},
        ]

        if source_id is not None:
            filters.append({"source_id": str(source_id)})

        if object_types:
            filters.append({
                "object_type": {"$in": object_types}
            })

        where_filter = (
            filters[0]
            if len(filters) == 1
            else {"$and": filters}
        )

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=actual_n,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        hits: list[RetrievalResult] = []
        if results.get("ids") and len(results["ids"]) > 0:
            for i, doc_id in enumerate(results["ids"][0]):
                hits.append(RetrievalResult(
                    id=doc_id,
                    text=results["documents"][0][i],
                    metadata=results["metadatas"][0][i],
                    distance=results["distances"][0][i],
                ))
        return hits

    def delete(
        self,
        tenant_id: str | uuid.UUID,
        object_id: str,
        source_id: str | uuid.UUID | None = None
    ) -> None:
        """Remove a single vector by its object ID."""
        col_name = _collection_name(tenant_id, source_id=source_id)
        if self._client is None:
            if col_name in self._fallback_store and object_id in self._fallback_store[col_name]:
                del self._fallback_store[col_name][object_id]
            return
        collection = self._get_or_create_collection(tenant_id, source_id=source_id)
        collection.delete(ids=[object_id])

    def count(
        self,
        tenant_id: str | uuid.UUID,
        source_id: str | uuid.UUID | None = None
    ) -> int:
        """Return the number of vectors in the collection."""
        col_name = _collection_name(tenant_id, source_id=source_id)
        if self._client is None:
            return len(self._fallback_store.get(col_name, {}))
        collection = self._get_or_create_collection(tenant_id, source_id=source_id)
        return collection.count()

