import uuid
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db import get_session
from app.semantic.review_service import SemanticReviewService
from app.semantic.version_service import VersionService

router = APIRouter(prefix="/api/v1/semantics", tags=["Semantic Review Engine"])

class ReviewActionPayload(BaseModel):
    actor: str
    reason: Optional[str] = None

class ReviewUpdatePayload(BaseModel):
    actor: str
    reason: Optional[str] = None
    updates: Dict[str, Any]

class RollbackPayload(BaseModel):
    source_id: uuid.UUID
    target_version: int
    actor: str

@router.get("/{tenant_id}/models/{semantic_model_id}/review/pending")
def get_pending_reviews(tenant_id: uuid.UUID, semantic_model_id: uuid.UUID, db: Session = Depends(get_session)):
    """Fetches all semantic objects that require review."""
    return SemanticReviewService.get_pending_reviews(db, tenant_id, semantic_model_id)

@router.post("/{tenant_id}/review/{object_type}/{object_id}/approve")
def approve_semantic_object(
    tenant_id: uuid.UUID, object_type: str, object_id: uuid.UUID, 
    payload: ReviewActionPayload, db: Session = Depends(get_session)
):
    """Approves a semantic object and moves it to ACTIVE state."""
    obj = SemanticReviewService.approve_object(db, tenant_id, object_type, object_id, payload.actor, payload.reason)
    return {"status": "success", "object_id": str(obj.id), "review_status": obj.review_status}

@router.post("/{tenant_id}/review/{object_type}/{object_id}/reject")
def reject_semantic_object(
    tenant_id: uuid.UUID, object_type: str, object_id: uuid.UUID, 
    payload: ReviewActionPayload, db: Session = Depends(get_session)
):
    """Rejects a semantic object and moves it to ARCHIVED state."""
    obj = SemanticReviewService.reject_object(db, tenant_id, object_type, object_id, payload.actor, payload.reason)
    return {"status": "success", "object_id": str(obj.id), "review_status": obj.review_status}

@router.put("/{tenant_id}/review/{object_type}/{object_id}")
def update_semantic_object(
    tenant_id: uuid.UUID, object_type: str, object_id: uuid.UUID, 
    payload: ReviewUpdatePayload, db: Session = Depends(get_session)
):
    """Updates a semantic object (e.g., editing a formula or renaming), saving feedback and bumping version."""
    obj = SemanticReviewService.update_object(db, tenant_id, object_type, object_id, payload.updates, payload.actor, payload.reason)
    return {"status": "success", "object_id": str(obj.id), "review_status": obj.review_status}

@router.post("/{tenant_id}/version/rollback")
def rollback_semantic_model(
    tenant_id: uuid.UUID, payload: RollbackPayload, db: Session = Depends(get_session)
):
    """Rolls back the active semantic model to a previous version."""
    model = VersionService.rollback_semantic_model(db, tenant_id, payload.source_id, payload.target_version, payload.actor)
    return {"status": "success", "active_model_id": str(model.id), "version": model.semantic_version}
