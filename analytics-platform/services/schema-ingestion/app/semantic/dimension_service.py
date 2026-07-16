import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SemanticDimension
from app.semantic.version_service import VersionService


class DimensionService:
    @staticmethod
    def create_dimension(db: Session, tenant_id: uuid.UUID, actor: str, **kwargs) -> SemanticDimension:
        business_name = kwargs.get("business_name")

        # Unique across tenant (optional, usually dimensions are unique by name)
        existing = db.scalar(select(SemanticDimension).where(
            SemanticDimension.tenant_id == tenant_id,
            SemanticDimension.business_name == business_name
        ))
        if existing:
            raise HTTPException(status_code=400, detail=f"Dimension '{business_name}' already exists")

        dim = SemanticDimension(
            tenant_id=tenant_id,
            created_by=actor,
            updated_by=actor,
            version=1,
            **kwargs
        )
        db.add(dim)
        db.flush()

        VersionService.snapshot_dimension(db, dim, change_reason="Initial creation", actor=actor)
        db.commit()
        db.refresh(dim)
        return dim

    @staticmethod
    def get_dimension(db: Session, tenant_id: uuid.UUID, dim_id: uuid.UUID) -> SemanticDimension:
        dim = db.scalar(select(SemanticDimension).where(
            SemanticDimension.id == dim_id,
            SemanticDimension.tenant_id == tenant_id
        ))
        if not dim:
            raise HTTPException(status_code=404, detail="Dimension not found")
        return dim

    @staticmethod
    def list_dimensions(db: Session, tenant_id: uuid.UUID) -> list[SemanticDimension]:
        return db.scalars(select(SemanticDimension).where(SemanticDimension.tenant_id == tenant_id)).all()
