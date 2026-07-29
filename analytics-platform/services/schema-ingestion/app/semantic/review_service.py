import uuid
import structlog
from fastapi import HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.models import SemanticMetric, SemanticDimension, SemanticKPI, SemanticJoin, BusinessGlossary
from app.semantic.feedback_service import FeedbackService
from app.semantic.audit_service import AuditService
from app.semantic.version_service import VersionService

logger = structlog.get_logger(__name__)

class SemanticReviewService:
    """
    Orchestrates user review of semantic fragments.
    """

    _MODEL_MAP = {
        "metric": SemanticMetric,
        "dimension": SemanticDimension,
        "kpi": SemanticKPI,
        "relationship": SemanticJoin,
        "glossary": BusinessGlossary
    }

    @classmethod
    def _get_object(cls, db: Session, object_type: str, object_id: uuid.UUID):
        model_cls = cls._MODEL_MAP.get(object_type.lower())
        if not model_cls:
            raise HTTPException(status_code=400, detail=f"Unsupported object_type: {object_type}")
        
        obj = db.query(model_cls).filter(model_cls.id == object_id).first()
        if not obj:
            raise HTTPException(status_code=404, detail=f"{object_type} {object_id} not found")
        return obj

    @classmethod
    def approve_object(cls, db: Session, tenant_id: uuid.UUID, object_type: str, object_id: uuid.UUID, actor: str, reason: str = None):
        obj = cls._get_object(db, object_type, object_id)
        
        old_status = obj.review_status
        if old_status == "ACTIVE":
            return obj
            
        obj.review_status = "ACTIVE"
        
        FeedbackService.capture_feedback(
            db=db, tenant_id=tenant_id, semantic_model_id=obj.semantic_model_id,
            object_type=object_type, object_id=object_id, user_id=actor, reason=reason or "Approved",
            old_state={"review_status": old_status}, new_state={"review_status": "ACTIVE"}
        )
        
        AuditService.log_action(
            db=db, tenant_id=tenant_id, entity_type=object_type, entity_id=object_id,
            action="APPROVE", actor=actor, reason=reason,
            before_state={"review_status": old_status}, after_state={"review_status": "ACTIVE"}
        )
        
        db.flush()
        return obj

    @classmethod
    def reject_object(cls, db: Session, tenant_id: uuid.UUID, object_type: str, object_id: uuid.UUID, actor: str, reason: str = None):
        obj = cls._get_object(db, object_type, object_id)
        
        old_status = obj.review_status
        if old_status in ["ARCHIVED", "REJECTED"]:
            return obj
            
        obj.review_status = "ARCHIVED"
        
        FeedbackService.capture_feedback(
            db=db, tenant_id=tenant_id, semantic_model_id=obj.semantic_model_id,
            object_type=object_type, object_id=object_id, user_id=actor, reason=reason or "Rejected",
            old_state={"review_status": old_status}, new_state={"review_status": "ARCHIVED"}
        )
        
        AuditService.log_action(
            db=db, tenant_id=tenant_id, entity_type=object_type, entity_id=object_id,
            action="REJECT", actor=actor, reason=reason,
            before_state={"review_status": old_status}, after_state={"review_status": "ARCHIVED"}
        )
        
        db.flush()
        return obj

    @classmethod
    def update_object(cls, db: Session, tenant_id: uuid.UUID, object_type: str, object_id: uuid.UUID, updates: Dict[str, Any], actor: str, reason: str = None):
        obj = cls._get_object(db, object_type, object_id)
        
        old_state = {}
        new_state = {}
        
        for k, v in updates.items():
            if hasattr(obj, k):
                old_val = getattr(obj, k)
                if old_val != v:
                    old_state[k] = old_val
                    new_state[k] = v
                    setattr(obj, k, v)
                    
        if not new_state:
            return obj # No changes
            
        if hasattr(obj, 'version'):
            obj.version += 1
            
        obj.review_status = "ACTIVE"
        
        # Take Snapshot if supported
        if object_type == "metric":
            VersionService.snapshot_metric(db, obj, reason or "Manual update", actor)
        elif object_type == "dimension":
            VersionService.snapshot_dimension(db, obj, reason or "Manual update", actor)
        elif object_type == "relationship":
            VersionService.snapshot_join(db, obj, reason or "Manual update", actor)
            
        FeedbackService.capture_feedback(
            db=db, tenant_id=tenant_id, semantic_model_id=obj.semantic_model_id,
            object_type=object_type, object_id=object_id, user_id=actor, reason=reason or "Manual update",
            old_state=old_state, new_state=new_state
        )
        
        AuditService.log_action(
            db=db, tenant_id=tenant_id, entity_type=object_type, entity_id=object_id,
            action="UPDATE", actor=actor, reason=reason,
            before_state=old_state, after_state=new_state
        )
        
        db.flush()
        return obj

    @classmethod
    def get_pending_reviews(cls, db: Session, tenant_id: uuid.UUID, semantic_model_id: uuid.UUID):
        results = {}
        for obj_type, model_cls in cls._MODEL_MAP.items():
            query = db.query(model_cls).filter(
                model_cls.semantic_model_id == semantic_model_id,
                model_cls.review_status.in_(["REVIEW_REQUIRED", "DRAFT"])
            )
            if hasattr(model_cls, 'tenant_id'):
                query = query.filter(model_cls.tenant_id == tenant_id)
            
            results[obj_type] = [VersionService._model_to_dict(x) for x in query.all()]
            
        return results
