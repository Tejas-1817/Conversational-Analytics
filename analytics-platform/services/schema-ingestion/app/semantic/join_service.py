import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SemanticJoin
from app.semantic.version_service import VersionService


class JoinService:
    @staticmethod
    def create_join(db: Session, tenant_id: uuid.UUID, actor: str, **kwargs) -> SemanticJoin:
        join = SemanticJoin(
            tenant_id=tenant_id,
            created_by=actor,
            updated_by=actor,
            version=1,
            **kwargs
        )
        db.add(join)
        db.flush()

        VersionService.snapshot_join(db, join, change_reason="Initial creation", actor=actor)
        db.commit()
        db.refresh(join)
        return join

    @staticmethod
    def get_join(db: Session, tenant_id: uuid.UUID, join_id: uuid.UUID) -> SemanticJoin:
        join = db.scalar(select(SemanticJoin).where(
            SemanticJoin.id == join_id,
            SemanticJoin.tenant_id == tenant_id
        ))
        if not join:
            raise HTTPException(status_code=404, detail="Join not found")
        return join

    @staticmethod
    def list_joins(db: Session, tenant_id: uuid.UUID) -> list[SemanticJoin]:
        return db.scalars(select(SemanticJoin).where(SemanticJoin.tenant_id == tenant_id)).all()
