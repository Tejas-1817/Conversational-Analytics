from typing import List
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_session
from app.api.deps import get_current_user, require_analyst
from app.models import User
from app.schemas_semantic import (
    SemanticMetricCreate, SemanticMetricOut,
    SemanticDimensionCreate, SemanticDimensionOut,
    SemanticJoinCreate, SemanticJoinOut,
    BusinessGlossaryCreate, BusinessGlossaryOut,
    MetricVersionOut
)
from app.semantic.metric_service import MetricService
from app.semantic.dimension_service import DimensionService
from app.semantic.join_service import JoinService
from app.semantic.glossary_service import GlossaryService
from app.semantic.synonym_service import SynonymService
from pydantic import BaseModel

router = APIRouter(prefix="/semantic", tags=["semantic"])

# --- Metrics ---

@router.post("/metrics", response_model=SemanticMetricOut, dependencies=[Depends(require_analyst)])
def create_metric(req: SemanticMetricCreate, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return MetricService.create_metric(db, user.tenant_id, user.email, **req.model_dump())

@router.put("/metrics/{metric_id}", response_model=SemanticMetricOut, dependencies=[Depends(require_analyst)])
def update_metric(metric_id: uuid.UUID, req: SemanticMetricCreate, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return MetricService.update_metric(db, user.tenant_id, metric_id, user.email, **req.model_dump())

@router.get("/metrics", response_model=List[SemanticMetricOut])
def list_metrics(db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return MetricService.list_metrics(db, user.tenant_id)

@router.get("/metrics/{metric_id}", response_model=SemanticMetricOut)
def get_metric(metric_id: uuid.UUID, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return MetricService.get_metric(db, user.tenant_id, metric_id)

@router.delete("/metrics/{metric_id}", dependencies=[Depends(require_analyst)])
def delete_metric(metric_id: uuid.UUID, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    MetricService.delete_metric(db, user.tenant_id, metric_id, user.email)
    return {"status": "deleted"}

@router.get("/metrics/{metric_id}/versions", response_model=List[MetricVersionOut])
def get_metric_versions(metric_id: uuid.UUID, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return MetricService.get_versions(db, user.tenant_id, metric_id)

@router.post("/metrics/{metric_id}/rollback", response_model=SemanticMetricOut, dependencies=[Depends(require_analyst)])
def rollback_metric(metric_id: uuid.UUID, version: int, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return MetricService.rollback_metric(db, user.tenant_id, metric_id, version, user.email)


# --- Dimensions ---

@router.post("/dimensions", response_model=SemanticDimensionOut, dependencies=[Depends(require_analyst)])
def create_dimension(req: SemanticDimensionCreate, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return DimensionService.create_dimension(db, user.tenant_id, user.email, **req.model_dump())

@router.get("/dimensions", response_model=List[SemanticDimensionOut])
def list_dimensions(db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return DimensionService.list_dimensions(db, user.tenant_id)

@router.put("/dimensions/{dim_id}", response_model=SemanticDimensionOut, dependencies=[Depends(require_analyst)])
def update_dimension(dim_id: uuid.UUID, req: SemanticDimensionCreate, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    dim = DimensionService.get_dimension(db, user.tenant_id, dim_id)
    for k, v in req.model_dump().items():
        setattr(dim, k, v)
    dim.version += 1
    db.commit()
    db.refresh(dim)
    return dim

@router.delete("/dimensions/{dim_id}", dependencies=[Depends(require_analyst)])
def delete_dimension(dim_id: uuid.UUID, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    dim = DimensionService.get_dimension(db, user.tenant_id, dim_id)
    db.delete(dim)
    db.commit()
    return {"status": "deleted"}


# --- Joins ---

@router.post("/joins", response_model=SemanticJoinOut, dependencies=[Depends(require_analyst)])
def create_join(req: SemanticJoinCreate, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return JoinService.create_join(db, user.tenant_id, user.email, **req.model_dump())

@router.get("/joins", response_model=List[SemanticJoinOut])
def list_joins(db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return JoinService.list_joins(db, user.tenant_id)

@router.put("/joins/{join_id}", response_model=SemanticJoinOut, dependencies=[Depends(require_analyst)])
def update_join(join_id: uuid.UUID, req: SemanticJoinCreate, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    join = JoinService.get_join(db, user.tenant_id, join_id)
    for k, v in req.model_dump().items():
        setattr(join, k, v)
    join.version += 1
    db.commit()
    db.refresh(join)
    return join

@router.delete("/joins/{join_id}", dependencies=[Depends(require_analyst)])
def delete_join(join_id: uuid.UUID, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    join = JoinService.get_join(db, user.tenant_id, join_id)
    db.delete(join)
    db.commit()
    return {"status": "deleted"}


# --- Glossary ---

@router.post("/glossary", response_model=BusinessGlossaryOut, dependencies=[Depends(require_analyst)])
def create_term(req: BusinessGlossaryCreate, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return GlossaryService.create_term(db, user.tenant_id, user.email, **req.model_dump())

@router.get("/glossary", response_model=List[BusinessGlossaryOut])
def list_terms(db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return GlossaryService.list_terms(db, user.tenant_id)

@router.put("/glossary/{term_id}", response_model=BusinessGlossaryOut, dependencies=[Depends(require_analyst)])
def update_term(term_id: uuid.UUID, req: BusinessGlossaryCreate, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    term = GlossaryService.get_term(db, user.tenant_id, term_id)
    for k, v in req.model_dump().items():
        setattr(term, k, v)
    db.commit()
    db.refresh(term)
    return term

@router.delete("/glossary/{term_id}", dependencies=[Depends(require_analyst)])
def delete_term(term_id: uuid.UUID, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    term = GlossaryService.get_term(db, user.tenant_id, term_id)
    db.delete(term)
    db.commit()
    return {"status": "deleted"}


# --- Synonyms ---
class SynonymCreate(BaseModel):
    synonym_term: str
    target_type: str
    target_id: uuid.UUID

@router.post("/synonyms", dependencies=[Depends(require_analyst)])
def add_synonym(req: SynonymCreate, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    syn = SynonymService.add_synonym(db, user.tenant_id, req.synonym_term, req.target_type, req.target_id, user.email)
    return {"id": syn.id, "synonym_term": syn.synonym}

@router.get("/synonyms/resolve")
def resolve_synonym(term: str, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return SynonymService.resolve_synonym(db, user.tenant_id, term)
