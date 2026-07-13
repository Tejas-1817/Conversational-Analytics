import uuid
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException

from app.models import BusinessGlossary

class GlossaryService:
    @staticmethod
    def create_term(db: Session, tenant_id: uuid.UUID, actor: str, **kwargs) -> BusinessGlossary:
        term = kwargs.get("term")
        existing = db.scalar(select(BusinessGlossary).where(
            BusinessGlossary.tenant_id == tenant_id, 
            BusinessGlossary.term == term
        ))
        if existing:
            raise HTTPException(status_code=400, detail=f"Term '{term}' already exists")
            
        glossary = BusinessGlossary(
            tenant_id=tenant_id,
            created_by=actor,
            updated_by=actor,
            **kwargs
        )
        db.add(glossary)
        db.commit()
        db.refresh(glossary)
        return glossary

    @staticmethod
    def get_term(db: Session, tenant_id: uuid.UUID, term_id: uuid.UUID) -> BusinessGlossary:
        term = db.scalar(select(BusinessGlossary).where(
            BusinessGlossary.id == term_id,
            BusinessGlossary.tenant_id == tenant_id
        ))
        if not term:
            raise HTTPException(status_code=404, detail="Glossary term not found")
        return term
        
    @staticmethod
    def list_terms(db: Session, tenant_id: uuid.UUID) -> List[BusinessGlossary]:
        return db.scalars(select(BusinessGlossary).where(BusinessGlossary.tenant_id == tenant_id)).all()
