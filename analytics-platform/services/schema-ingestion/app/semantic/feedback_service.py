import uuid
import structlog
from sqlalchemy.orm import Session
from app.models import SemanticFeedback

logger = structlog.get_logger(__name__)

class FeedbackService:
    """
    Persists customer-specific feedback into SemanticFeedback table.
    """
    
    @staticmethod
    def capture_feedback(
        db: Session,
        tenant_id: uuid.UUID,
        semantic_model_id: uuid.UUID,
        object_type: str,
        object_id: uuid.UUID,
        user_id: str,
        reason: str,
        old_state: dict,
        new_state: dict
    ):
        logger.info("capturing_semantic_feedback", object_type=object_type, object_id=str(object_id), user_id=user_id)
        
        feedback = SemanticFeedback(
            tenant_id=tenant_id,
            semantic_model_id=semantic_model_id,
            object_type=object_type,
            object_id=object_id,
            user_id=user_id,
            reason=reason,
            old_state=old_state,
            new_state=new_state
        )
        
        db.add(feedback)
        db.flush()
        return feedback
