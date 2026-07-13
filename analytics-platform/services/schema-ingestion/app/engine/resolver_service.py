import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, or_

from app.models import SemanticMetric, SemanticDimension, SemanticSynonym, BusinessGlossary
from app.schemas_engine import NLUIntent

class ResolutionResult:
    def __init__(self):
        self.metric: Optional[SemanticMetric] = None
        self.dimensions: List[SemanticDimension] = []
        self.unresolved_terms: List[str] = []
        self.ambiguities: List[str] = []

class ResolverService:
    @staticmethod
    def resolve_entities(db: Session, tenant_id: uuid.UUID, intent: NLUIntent) -> ResolutionResult:
        result = ResolutionResult()
        
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

    @staticmethod
    def _resolve_metric(db: Session, tenant_id: uuid.UUID, term: str) -> List[SemanticMetric]:
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
    def _resolve_dimension(db: Session, tenant_id: uuid.UUID, term: str) -> Optional[SemanticDimension]:
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
