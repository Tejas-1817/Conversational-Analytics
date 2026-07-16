import uuid

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models import BusinessGlossary, SemanticDimension, SemanticJoin, SemanticMetric, SemanticSynonym


class SynonymService:
    @staticmethod
    def add_synonym(db: Session, tenant_id: uuid.UUID, synonym_term: str, target_type: str, target_id: uuid.UUID, actor: str) -> SemanticSynonym:
        existing = db.scalar(select(SemanticSynonym).where(
            SemanticSynonym.tenant_id == tenant_id,
            SemanticSynonym.synonym == synonym_term
        ))
        if existing:
            raise HTTPException(status_code=400, detail=f"Synonym '{synonym_term}' already exists")

        # Validate target exists
        if target_type == "metric":
            target = db.scalar(select(SemanticMetric).where(and_(SemanticMetric.id == target_id, SemanticMetric.tenant_id == tenant_id)))
        elif target_type == "dimension":
            target = db.scalar(select(SemanticDimension).where(and_(SemanticDimension.id == target_id, SemanticDimension.tenant_id == tenant_id)))
        elif target_type == "join":
            target = db.scalar(select(SemanticJoin).where(and_(SemanticJoin.id == target_id, SemanticJoin.tenant_id == tenant_id)))
        elif target_type == "glossary":
            target = db.scalar(select(BusinessGlossary).where(and_(BusinessGlossary.id == target_id, BusinessGlossary.tenant_id == tenant_id)))
        else:
            raise HTTPException(status_code=400, detail="Invalid target type")

        if not target:
            raise HTTPException(status_code=404, detail=f"Target {target_type} not found")

        synonym = SemanticSynonym(
            tenant_id=tenant_id,
            synonym=synonym_term,
            entity_type=target_type.upper(),
            entity_id=target_id
        )
        db.add(synonym)
        db.commit()
        db.refresh(synonym)
        return synonym

    @staticmethod
    def resolve_synonym(db: Session, tenant_id: uuid.UUID, search_term: str):
        # Exact match
        syn = db.scalar(select(SemanticSynonym).where(
            SemanticSynonym.tenant_id == tenant_id,
            SemanticSynonym.synonym.ilike(search_term)
        ))
        if syn:
            return {"resolved": True, "target_type": syn.entity_type, "target_id": syn.entity_id}

        return {"resolved": False, "target_type": None, "target_id": None}

    @staticmethod
    def list_synonyms(db: Session, tenant_id: uuid.UUID) -> list[SemanticSynonym]:
        return db.scalars(select(SemanticSynonym).where(SemanticSynonym.tenant_id == tenant_id)).all()
