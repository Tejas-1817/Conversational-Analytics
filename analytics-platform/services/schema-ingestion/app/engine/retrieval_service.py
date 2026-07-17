"""RAG-based semantic retrieval service.

Given a query string and a tenant, this service:
  1. Embeds the query with the configured local embedding provider.
  2. Queries the tenant's Chroma collection (cosine-distance, top-k).
  3. Filters hits to those with distance <= rag_distance_threshold.
  4. Hydrates each hit's object_id back to the corresponding ORM object
     (bulk IN-query per type — single round-trip per type group).
  5. Returns a RetrievalHits dataclass consumed by ResolverService and
     PlannerService.

Invariants:
  - Tenant isolation: ChromaStore.query() always applies where={"tenant_id":...}.
  - Only APPROVED objects are ever in Chroma (enforced by Phase 2 embedding job).
  - No DB writes happen here.
  - Falls back gracefully (used_rag=False) when Chroma is empty or unavailable.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.embeddings.chroma_store import ChromaStore, RetrievalResult
from app.models import ApprovedSQLExample, BusinessGlossary, SemanticDimension, SemanticMetric, TableMeta

log = structlog.get_logger()


@dataclass
class RetrievalHits:
    """Hydrated results from a Chroma vector query, organised by object type."""
    metrics:    list[tuple[SemanticMetric, float]] = field(default_factory=list)
    dimensions: list[tuple[SemanticDimension, float]] = field(default_factory=list)
    tables:     list[tuple[TableMeta, float]] = field(default_factory=list)
    glossary:   list[tuple[BusinessGlossary, float]] = field(default_factory=list)
    approved_examples: list[tuple[ApprovedSQLExample, float]] = field(default_factory=list)
    raw_results: list[RetrievalResult] = field(default_factory=list)
    used_rag:   bool = False
    threshold:  float = 0.60


class RetrievalService:
    """Query the tenant's Chroma vector store and return hydrated ORM objects."""

    @staticmethod
    def retrieve(
        query_text: str,
        tenant_id: str | uuid.UUID,
        db: Session,
        store: ChromaStore | None = None,
    ) -> RetrievalHits:
        """Embed query_text, search Chroma, hydrate hits to ORM objects.

        Args:
            query_text: The user's natural-language question (full text, not just
                        the metric/dimension terms — richer context = better recall).
            tenant_id:  Tenant scope; enforced inside ChromaStore.
            db:         SQLAlchemy session for ORM hydration (read-only).
            store:      ChromaStore instance; defaults to PersistentClient from
                        settings. Pass an EphemeralClient store for tests.

        Returns:
            RetrievalHits with used_rag=False if RAG is globally disabled,
            Chroma is empty, or any exception occurs (safe fallback to keyword path).
        """
        settings = get_settings()
        hits = RetrievalHits(threshold=settings.rag_distance_threshold)

        if not settings.rag_enabled:
            log.debug("retrieval_service_disabled", reason="rag_enabled=False")
            return hits

        try:
            # 1. Embed the query
            from app.embeddings.registry import get_embedding_provider  # lazy import
            provider = get_embedding_provider()
            query_vec = provider.embed([query_text])[0]

            # 2. Open the store
            if store is None:
                store = ChromaStore(ephemeral=False)

            # 3. Query Chroma (tenant-isolated)
            raw: list[RetrievalResult] = store.query(
                tenant_id=tenant_id,
                query_embedding=query_vec,
                n_results=settings.rag_top_k,
            )

            if not raw:
                log.debug("retrieval_service_empty", tenant_id=str(tenant_id))
                return hits

            # 4. Filter by distance threshold
            above_threshold = [r for r in raw if r.distance <= settings.rag_distance_threshold]
            if not above_threshold:
                log.debug(
                    "retrieval_service_no_hits_above_threshold",
                    threshold=settings.rag_distance_threshold,
                    closest_dist=raw[0].distance,
                )
                return hits

            hits.raw_results = above_threshold

            # 5. Group object IDs by type for bulk hydration
            metric_ids:    list[uuid.UUID] = []
            dimension_ids: list[uuid.UUID] = []
            table_ids:     list[uuid.UUID] = []
            glossary_ids:  list[uuid.UUID] = []
            example_ids:   list[uuid.UUID] = []
            dist_by_id:    dict[str, float] = {}

            for r in above_threshold:
                oid = r.metadata.get("object_id", "")
                otype = r.metadata.get("object_type", "")
                dist_by_id[oid] = r.distance
                try:
                    uid = uuid.UUID(oid)
                except (ValueError, AttributeError):
                    continue
                if otype == "metric":
                    metric_ids.append(uid)
                elif otype == "dimension":
                    dimension_ids.append(uid)
                elif otype == "table":
                    table_ids.append(uid)
                elif otype == "glossary":
                    glossary_ids.append(uid)
                elif otype == "approved_example":
                    example_ids.append(uid)
                # columns/synonyms/relationships: not directly useful for entity resolution

            # 6. Bulk hydrate — single IN-query per type
            if metric_ids:
                metrics = db.scalars(
                    select(SemanticMetric).where(SemanticMetric.id.in_(metric_ids))
                ).all()
                hits.metrics = [
                    (m, dist_by_id.get(str(m.id), 1.0)) for m in metrics
                ]
                # Sort by distance ascending (most relevant first)
                hits.metrics.sort(key=lambda t: t[1])

            if dimension_ids:
                dims = db.scalars(
                    select(SemanticDimension).where(SemanticDimension.id.in_(dimension_ids))
                ).all()
                hits.dimensions = [
                    (d, dist_by_id.get(str(d.id), 1.0)) for d in dims
                ]
                hits.dimensions.sort(key=lambda t: t[1])

            if table_ids:
                tables = db.scalars(
                    select(TableMeta).where(TableMeta.id.in_(table_ids))
                ).all()
                hits.tables = [
                    (t, dist_by_id.get(str(t.id), 1.0)) for t in tables
                ]
                hits.tables.sort(key=lambda t: t[1])

            if glossary_ids:
                glossary = db.scalars(
                    select(BusinessGlossary).where(BusinessGlossary.id.in_(glossary_ids))
                ).all()
                hits.glossary = [
                    (g, dist_by_id.get(str(g.id), 1.0)) for g in glossary
                ]
                hits.glossary.sort(key=lambda t: t[1])

            if example_ids:
                examples = db.scalars(
                    select(ApprovedSQLExample).where(ApprovedSQLExample.id.in_(example_ids))
                ).all()
                hits.approved_examples = [
                    (e, dist_by_id.get(str(e.id), 1.0)) for e in examples
                ]
                hits.approved_examples.sort(key=lambda t: t[1])

            hits.used_rag = True
            log.info(
                "retrieval_service_hits",
                tenant_id=str(tenant_id),
                metrics=len(hits.metrics),
                dimensions=len(hits.dimensions),
                tables=len(hits.tables),
                glossary=len(hits.glossary),
            )

        except Exception as exc:
            log.warning(
                "retrieval_service_fallback",
                reason=str(exc),
                tenant_id=str(tenant_id),
            )
            # Return an empty hits object — ResolverService will fall back to keyword path
            return RetrievalHits(threshold=get_settings().rag_distance_threshold)

        return hits
