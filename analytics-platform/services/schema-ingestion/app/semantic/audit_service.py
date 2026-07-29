import uuid
import structlog
from sqlalchemy.orm import Session
from app.models import AuditLog

logger = structlog.get_logger(__name__)

class AuditService:
    """
    Maintains complete audit history: Who changed, What changed, Why it changed, When it changed.
    """
    
    @staticmethod
    def log_action(
        db: Session,
        tenant_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
        action: str,
        actor: str,
        reason: str = None,
        before_state: dict = None,
        after_state: dict = None
    ):
        logger.info("audit_log_created", entity_type=entity_type, entity_id=str(entity_id), action=action, actor=actor)
        
        if reason:
            after_state = after_state or {}
            after_state["_reason"] = reason
            
        audit_entry = AuditLog(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor=actor,
            before=before_state,
            after=after_state,
            event_type="semantic_review"
        )
        
        db.add(audit_entry)
        db.flush()
        return audit_entry
