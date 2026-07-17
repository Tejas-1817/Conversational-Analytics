import uuid

import structlog
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import SemanticDimension, SemanticMetric, SemanticSynonym, SemanticKPI, BusinessGlossary
from app.schemas_engine import NLUIntent
from app.engine.semantic_cache import semantic_cache

log = structlog.get_logger()


class ResolutionResult:
    def __init__(self):
        self.kpi: SemanticKPI | None = None
        self.metric: SemanticMetric | None = None
        self.dimensions: list[SemanticDimension] = []
        self.unresolved_terms: list[str] = []; self.ambiguities: list[str] = []
        self.retrieval_path: str = "keyword"   # "rag" | "keyword" | "hybrid"

class ResolverService:
    @staticmethod
    def resolve_entities(
        db: Session,
        tenant_id: uuid.UUID,
        intent: NLUIntent,
        rag_hits=None,      # RetrievalHits | None — injected by engine.py
    ) -> ResolutionResult:
        """Resolve NLU entities to ORM objects using a hybrid RAG + keyword strategy.

        Resolution order:
          1. If rag_hits.used_rag is True: try to match intent terms against
             RAG candidates (already filtered to distance <= threshold).
          2. If RAG finds nothing useful (or rag_hits is None / used_rag=False):
             fall back to the existing ILIKE + synonym keyword path.

        The keyword path is NEVER removed — it is always the safety net.
        """
        result = ResolutionResult()

        # ------------------------------------------------------------------ #
        # STEP 1 — RAG path: use Chroma-retrieved candidates                 #
        # ------------------------------------------------------------------ #
        if rag_hits is not None and rag_hits.used_rag:
            rag_metric_found = False
            rag_dim_found    = False

            # Metric resolution via RAG candidates
            if intent.metric and rag_hits.metrics:
                best = ResolverService._pick_best_metric(rag_hits.metrics, intent.metric)
                if best:
                    result.metric = best
                    rag_metric_found = True

            # KPI: RAG doesn't surface KPIs (not in embedding job) — skip to keyword
            if intent.kpi:
                kpis = ResolverService._resolve_kpi(db, tenant_id, intent.kpi)
                if len(kpis) == 1:
                    result.kpi = kpis[0]
                elif len(kpis) > 1:
                    result.ambiguities.append(
                        f"Multiple KPIs found for '{intent.kpi}': {', '.join(k.name for k in kpis)}"
                    )
                else:
                    result.unresolved_terms.append(intent.kpi)

            # Dimension resolution via RAG candidates
            if intent.dimensions:
                matched_dims, unmatched = ResolverService._pick_dimensions_from_rag(
                    rag_hits.dimensions, intent.dimensions
                )
                result.dimensions.extend(matched_dims)
                if matched_dims:
                    rag_dim_found = True
                # For unmatched dims: keyword fallback
                for dim_name in unmatched:
                    dim = ResolverService._resolve_dimension(db, tenant_id, dim_name)
                    if dim:
                        result.dimensions.append(dim)
                    else:
                        result.unresolved_terms.append(dim_name)

            # Decide path label
            if rag_metric_found or rag_dim_found:
                # If metric was also needed but RAG missed it, try keyword for that
                if intent.metric and not result.metric:
                    metrics = ResolverService._resolve_metric(db, tenant_id, intent.metric)
                    if len(metrics) == 1:
                        result.metric = metrics[0]
                    elif len(metrics) > 1:
                        result.ambiguities.append(
                            f"Multiple metrics found for '{intent.metric}': "
                            f"{', '.join(m.name for m in metrics)}"
                        )
                    else:
                        result.unresolved_terms.append(intent.metric)
                result.retrieval_path = "rag"
                log.info("resolver_path", path="rag", tenant_id=str(tenant_id))
                return result

        # ------------------------------------------------------------------ #
        # STEP 2 — Keyword fallback (original ILIKE + synonym path, intact)  #
        # ------------------------------------------------------------------ #
        result.retrieval_path = "keyword"
        log.info("resolver_path", path="keyword", tenant_id=str(tenant_id))

        # Resolve KPI
        if intent.kpi:
            kpis = ResolverService._resolve_kpi(db, tenant_id, intent.kpi)
            if len(kpis) == 1:
                result.kpi = kpis[0]
            elif len(kpis) > 1:
                names = [k.name for k in kpis]
                result.ambiguities.append(f"Multiple KPIs found for '{intent.kpi}': {', '.join(names)}")
            else:
                result.unresolved_terms.append(intent.kpi)

        # Resolve Metric
        if intent.metric:
            metrics = ResolverService._resolve_metric(db, tenant_id, intent.metric)
            if len(metrics) == 1:
                result.metric = metrics[0]
            elif len(metrics) > 1:
                names = [m.name for m in metrics]
                result.ambiguities.append(f"Multiple metrics found for '{intent.metric}': {', '.join(names)}")
            else:
                result.unresolved_terms.append(intent.metric)

        # Resolve Dimensions
        for dim_name in intent.dimensions:
            dim = ResolverService._resolve_dimension(db, tenant_id, dim_name)
            if dim:
                result.dimensions.append(dim)
            else:
                result.unresolved_terms.append(dim_name)

        return result

    # ------------------------------------------------------------------ #
    # RAG helper: pick the best metric from RAG candidates                #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _pick_best_metric(
        rag_metrics: list,      # list[tuple[SemanticMetric, float]]
        intent_term: str,
    ) -> SemanticMetric | None:
        """Return the closest RAG metric to the intent term.

        Preference order:
          1. Exact name/business_name match (case-insensitive)
          2. Substring match in name or business_name
          3. Lowest distance (first in already-sorted list)
        """
        t = intent_term.lower()
        # Exact match
        for m, _ in rag_metrics:
            if m.name.lower() == t or (m.business_name and m.business_name.lower() == t):
                return m
        # Substring
        for m, _ in rag_metrics:
            if t in m.name.lower() or (m.business_name and t in m.business_name.lower()):
                return m
        # Closest vector (first in sorted list)
        if rag_metrics:
            return rag_metrics[0][0]
        return None

    @staticmethod
    def _pick_dimensions_from_rag(
        rag_dims: list,         # list[tuple[SemanticDimension, float]]
        intent_dim_names: list[str],
    ) -> tuple[list[SemanticDimension], list[str]]:
        """Match each intent dimension name against RAG dimension candidates.

        Returns (matched, unmatched_names).
        unmatched_names will be retried via the keyword path.
        """
        matched: list[SemanticDimension] = []
        unmatched: list[str] = []
        used_ids: set = set()

        for dim_name in intent_dim_names:
            t = dim_name.lower()
            found = None
            # 1. Exact match
            for d, _ in rag_dims:
                if d.id not in used_ids and d.business_name.lower() == t:
                    found = d
                    break
            # 2. Substring
            if not found:
                for d, _ in rag_dims:
                    if d.id not in used_ids and t in d.business_name.lower():
                        found = d
                        break
            if found:
                matched.append(found)
                used_ids.add(found.id)
            else:
                unmatched.append(dim_name)

        return matched, unmatched

    # ------------------------------------------------------------------ #
    # Keyword helpers (unchanged from original)                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _resolve_metric(db: Session, tenant_id: uuid.UUID, term: str) -> list[SemanticMetric]:
        # 1. Exact match by name or business_name
        metrics = db.scalars(select(SemanticMetric).where(
            SemanticMetric.tenant_id == tenant_id,
            or_(
                SemanticMetric.name.ilike(f"%{term}%"),
                SemanticMetric.business_name.ilike(f"%{term}%")
            )
        )).all()

        if metrics:
            # If there's an exact match, prefer it
            exact = [m for m in metrics if m.name.lower() == term.lower() or (m.business_name and m.business_name.lower() == term.lower())]
            return exact if exact else list(metrics)

        # 2. Check synonyms
        syns = db.scalars(select(SemanticSynonym).where(
            SemanticSynonym.tenant_id == tenant_id,
            SemanticSynonym.synonym.ilike(term),
            SemanticSynonym.entity_type == "METRIC"
        )).all()

        if syns:
            ids = [s.entity_id for s in syns]
            return list(db.scalars(select(SemanticMetric).where(
                SemanticMetric.id.in_(ids),
                SemanticMetric.tenant_id == tenant_id
            )).all())

        return []

    @staticmethod
    def _resolve_dimension(db: Session, tenant_id: uuid.UUID, term: str) -> SemanticDimension | None:
        dim = db.scalar(select(SemanticDimension).where(
            SemanticDimension.tenant_id == tenant_id,
            SemanticDimension.business_name.ilike(term)
        ))
        if dim:
            return dim

        # Check synonyms
        syn = db.scalar(select(SemanticSynonym).where(
            SemanticSynonym.tenant_id == tenant_id,
            SemanticSynonym.synonym.ilike(term),
            SemanticSynonym.entity_type == "DIMENSION"
        ))
        if syn:
            return db.scalar(select(SemanticDimension).where(
                SemanticDimension.id == syn.entity_id,
                SemanticDimension.tenant_id == tenant_id
            ))

        return None

    @staticmethod
    def _resolve_kpi(db: Session, tenant_id: uuid.UUID, term: str) -> list[SemanticKPI]:
        from app.models import SemanticModel
        kpis = db.scalars(select(SemanticKPI).join(
                SemanticModel, SemanticKPI.semantic_model_id == SemanticModel.id
            ).where(
                SemanticKPI.name.ilike(f"%{term}%"),
                SemanticModel.tenant_id == tenant_id
            )
        ).all()
        
        if kpis:
            exact = [k for k in kpis if k.name.lower() == term.lower()]
            return exact if exact else list(kpis)
            
        return []


