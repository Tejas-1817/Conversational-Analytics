import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SemanticJoin
from app.semantic.version_service import VersionService

_PROTECTED_FIELDS = {"status", "tenant_id", "created_by", "id"}


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

    @staticmethod
    def update_join(
        db: Session,
        tenant_id: uuid.UUID,
        join_id: uuid.UUID,
        actor: str,
        **kwargs,
    ) -> SemanticJoin:
        """Update mutable join fields. Status cannot be changed here."""
        join = JoinService.get_join(db, tenant_id, join_id)
        for field in _PROTECTED_FIELDS:
            if field in kwargs:
                raise ValueError(
                    f"Field '{field}' cannot be set via update; "
                    "use the dedicated approve/reject endpoint."
                )
        for k, v in kwargs.items():
            setattr(join, k, v)
        join.version += 1
        join.updated_by = actor
        db.commit()
        db.refresh(join)
        return join

    @staticmethod
    def approve_join(
        db: Session,
        tenant_id: uuid.UUID,
        join_id: uuid.UUID,
        actor: str,
    ) -> SemanticJoin:
        """Transition a join to 'approved'. Only path that may set status='approved'."""
        join = JoinService.get_join(db, tenant_id, join_id)
        if join.status == "approved":
            return join  # idempotent
        join.status = "approved"
        join.updated_by = actor
        join.version += 1
        db.flush()
        VersionService.snapshot_join(db, join, change_reason="Approved", actor=actor)
        db.commit()
        db.refresh(join)
        return join

