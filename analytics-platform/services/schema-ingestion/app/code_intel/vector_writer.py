"""Embed code chunks using Google text-embedding-004 and store in ChromaDB.

Reuses the existing ChromaStore infrastructure from app.embeddings.chroma_store.
"""
from __future__ import annotations

import structlog

from app.config import get_settings
from app.code_intel.code_chunker import CodeChunk
from app.embeddings.chroma_store import ChromaStore, EmbeddedObject

log = structlog.get_logger(__name__)

# Batch size for embedding API calls (Google limits to 100 per request)
EMBED_BATCH_SIZE = 50


class VectorWriter:
    """Embed code chunks via Gemini and store them in ChromaDB."""

    def __init__(self) -> None:
        settings = get_settings()
        self._chroma = ChromaStore()
        self._api_key = settings.gemini_api_key

        # Lazy-load the Gemini client
        self._client = None

    def _get_client(self):
        """Lazy-initialize the Gemini client."""
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts using the platform's local sentence-transformers provider."""
        from app.embeddings.registry import get_embedding_provider
        
        provider = get_embedding_provider()
        return provider.embed(texts)

    # ------------------------------------------------------------------
    # Store
    # ------------------------------------------------------------------

    def store_chunks(
        self,
        tenant_id: str,
        repo_id: str,
        chunks: list[CodeChunk],
    ) -> int:
        """Embed and store code chunks into ChromaDB.

        Uses a dedicated collection per repo to keep code vectors
        separate from domain document vectors.

        Returns the number of chunks stored.
        """
        if not chunks:
            return 0

        # Prepare texts for embedding — include file path as context
        texts = [
            f"# File: {chunk.file_path}\n"
            f"# Type: {chunk.chunk_type} | Name: {chunk.name}\n\n"
            f"{chunk.text}"
            for chunk in chunks
        ]

        # Generate embeddings
        log.info("embedding_code_chunks", count=len(chunks), repo_id=repo_id)
        embeddings = self.embed_texts(texts)

        # Build EmbeddedObject list for ChromaStore
        objects: list[EmbeddedObject] = []
        for chunk, embedding in zip(chunks, embeddings):
            meta = {
                "tenant_id": str(tenant_id),
                "repo_id": repo_id,
                "file_path": chunk.file_path,
                "chunk_type": chunk.chunk_type,
                "name": chunk.name,
                "line_start": chunk.line_start,
                "line_end": chunk.line_end,
                "language": chunk.language,
                "object_type": "code_chunk",
            }

            objects.append(EmbeddedObject(
                id=chunk.id,
                text=chunk.text,
                embedding=embedding,
                metadata=meta,
            ))

        # Upsert into ChromaDB using a repo-specific source_id
        count = self._chroma.upsert(
            tenant_id=tenant_id,
            objects=objects,
            source_id=repo_id,  # Separate collection per repo
        )

        log.info("code_chunks_stored", count=count, repo_id=repo_id)
        return count

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_file_chunks(
        self, tenant_id: str, repo_id: str, file_path: str,
    ) -> None:
        """Remove all chunks for a specific file from ChromaDB.

        Note: ChromaDB doesn't support metadata-based deletion directly
        on all backends, so we query first then delete by IDs.
        """
        # For now, we'll handle this during re-ingestion by upserting
        # with the same IDs (which overwrites old data)
        log.info("file_chunks_deletion_requested", file_path=file_path)

    def delete_repo_chunks(self, tenant_id: str, repo_id: str) -> None:
        """Remove all code chunks for a repository."""
        log.info("repo_chunks_deletion_requested", repo_id=repo_id)

    # ------------------------------------------------------------------
    # Query (for GraphRAG retrieval)
    # ------------------------------------------------------------------

    def search_code(
        self,
        tenant_id: str,
        repo_id: str,
        query: str,
        n_results: int = 6,
    ) -> list[dict]:
        """Search for code chunks semantically similar to the query.

        Returns a list of dicts with text, metadata, and distance.
        """
        # Embed the query
        query_embedding = self.embed_texts([query])[0]

        # Query ChromaDB
        from app.embeddings.chroma_store import RetrievalResult
        results = self._chroma.query(
            tenant_id=tenant_id,
            query_embedding=query_embedding,
            n_results=n_results,
            source_id=repo_id,
            object_types=["code_chunk"],
        )

        return [
            {
                "id": r.id,
                "text": r.text,
                "metadata": r.metadata,
                "distance": r.distance,
            }
            for r in results
        ]
