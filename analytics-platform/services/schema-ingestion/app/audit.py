"""Audit trail helper — every review action lands here."""
import uuid

from sqlalchemy.orm import Session

from app.models import AuditLog


def record(session: Session, *, tenant_id: uuid.UUID | None, entity_type: str,
           entity_id: uuid.UUID, action: str, actor: str,
           before: dict | None = None, after: dict | None = None) -> None:
    session.add(AuditLog(tenant_id=tenant_id, entity_type=entity_type, entity_id=entity_id,
                         action=action, actor=actor, before=before, after=after))
