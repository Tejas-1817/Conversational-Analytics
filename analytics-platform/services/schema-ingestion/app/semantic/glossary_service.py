import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BusinessGlossary

_PROTECTED_FIELDS = {"status", "tenant_id", "created_by", "id"}


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
    def list_terms(db: Session, tenant_id: uuid.UUID) -> list[BusinessGlossary]:
        return db.scalars(select(BusinessGlossary).where(BusinessGlossary.tenant_id == tenant_id)).all()

    @staticmethod
    def update_term(
        db: Session,
        tenant_id: uuid.UUID,
        term_id: uuid.UUID,
        actor: str,
        **kwargs,
    ) -> BusinessGlossary:
        """Update mutable glossary fields. Status cannot be changed here."""
        term = GlossaryService.get_term(db, tenant_id, term_id)
        for field in _PROTECTED_FIELDS:
            if field in kwargs:
                raise ValueError(
                    f"Field '{field}' cannot be set via update; "
                    "use the dedicated approve/reject endpoint."
                )
        for k, v in kwargs.items():
            setattr(term, k, v)
        term.updated_by = actor
        db.commit()
        db.refresh(term)
        return term

    @staticmethod
    def approve_term(
        db: Session,
        tenant_id: uuid.UUID,
        term_id: uuid.UUID,
        actor: str,
    ) -> BusinessGlossary:
        """Transition a glossary term to 'approved'. Only path that may set status='approved'."""
        term = GlossaryService.get_term(db, tenant_id, term_id)
        if term.status == "approved":
            return term  # idempotent
        term.status = "approved"
        term.updated_by = actor
        db.commit()
        db.refresh(term)
        return term

