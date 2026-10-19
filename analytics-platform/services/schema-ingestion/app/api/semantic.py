"""Semantic layer API — metrics, dimensions, joins, glossary, synonyms, approve endpoints.

Approval endpoints (POST …/approve) are the ONLY path that may set status='approved'.
Plain PUT endpoints are for editing content fields only; any attempt to write `status`
via PUT is rejected by the service layer with a ValueError → HTTP 400.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin, require_analyst
from app.db import get_session
from app.models import User, BusinessRule
from app.context_layer.feedback_loop import ContextLifecycleManager
from app.schemas_semantic import (
    BusinessGlossaryCreate,
    BusinessGlossaryOut,
    MetricVersionOut,
    SemanticDimensionCreate,
    SemanticDimensionOut,
    SemanticJoinCreate,
    SemanticJoinOut,
    SemanticMetricCreate,
    SemanticMetricOut,
)
from app.semantic.dimension_service import DimensionService
from app.semantic.glossary_service import GlossaryService
from app.semantic.join_service import JoinService
from app.semantic.metric_service import MetricService
from app.semantic.synonym_service import SynonymService

router = APIRouter(prefix="/semantic", tags=["semantic"])

# --- Metrics ---

@router.post("/metrics", response_model=SemanticMetricOut, dependencies=[Depends(require_analyst)])
def create_metric(
    req: SemanticMetricCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user)
):
    metric = MetricService.create_metric(db, user.tenant_id, user.email, **req.model_dump())
    background_tasks.add_task(_embed_tenant, str(user.tenant_id))
    return metric

@router.put("/metrics/{metric_id}", response_model=SemanticMetricOut, dependencies=[Depends(require_analyst)])
def update_metric(
    metric_id: uuid.UUID,
    req: SemanticMetricCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user)
):
    try:
        metric = MetricService.update_metric(db, user.tenant_id, metric_id, user.email, **req.model_dump())
        background_tasks.add_task(_embed_tenant, str(user.tenant_id))
        return metric
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.post(
    "/metrics/{metric_id}/approve",
    response_model=SemanticMetricOut,
    dependencies=[Depends(require_analyst)],
    summary="Approve a metric and trigger background embedding",
)
def approve_metric(
    metric_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Set metric status to 'approved' and enqueue embedding as a background task."""
    metric = MetricService.approve_metric(db, user.tenant_id, metric_id, user.email)
    background_tasks.add_task(_embed_tenant, str(user.tenant_id))
    return metric

@router.get("/metrics", response_model=list[SemanticMetricOut])
def list_metrics(db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return MetricService.list_metrics(db, user.tenant_id)

@router.get("/metrics/{metric_id}", response_model=SemanticMetricOut)
def get_metric(metric_id: uuid.UUID, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return MetricService.get_metric(db, user.tenant_id, metric_id)

@router.delete("/metrics/{metric_id}", dependencies=[Depends(require_analyst)])
def delete_metric(metric_id: uuid.UUID, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    MetricService.delete_metric(db, user.tenant_id, metric_id, user.email)
    return {"status": "deleted"}

@router.get("/metrics/{metric_id}/versions", response_model=list[MetricVersionOut])
def get_metric_versions(metric_id: uuid.UUID, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return MetricService.get_versions(db, user.tenant_id, metric_id)

@router.post("/metrics/{metric_id}/rollback", response_model=SemanticMetricOut, dependencies=[Depends(require_analyst)])
def rollback_metric(metric_id: uuid.UUID, version: int, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return MetricService.rollback_metric(db, user.tenant_id, metric_id, version, user.email)


# --- Dimensions ---

@router.post("/dimensions", response_model=SemanticDimensionOut, dependencies=[Depends(require_analyst)])
def create_dimension(req: SemanticDimensionCreate, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return DimensionService.create_dimension(db, user.tenant_id, user.email, **req.model_dump())

@router.get("/dimensions", response_model=list[SemanticDimensionOut])
def list_dimensions(db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return DimensionService.list_dimensions(db, user.tenant_id)

@router.put("/dimensions/{dim_id}", response_model=SemanticDimensionOut, dependencies=[Depends(require_analyst)])
def update_dimension(dim_id: uuid.UUID, req: SemanticDimensionCreate, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    try:
        return DimensionService.update_dimension(db, user.tenant_id, dim_id, user.email, **req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.post(
    "/dimensions/{dim_id}/approve",
    response_model=SemanticDimensionOut,
    dependencies=[Depends(require_analyst)],
    summary="Approve a dimension and trigger background embedding",
)
def approve_dimension(
    dim_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    dim = DimensionService.approve_dimension(db, user.tenant_id, dim_id, user.email)
    background_tasks.add_task(_embed_tenant, str(user.tenant_id))
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

@router.get("/joins", response_model=list[SemanticJoinOut])
def list_joins(db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return JoinService.list_joins(db, user.tenant_id)

@router.put("/joins/{join_id}", response_model=SemanticJoinOut, dependencies=[Depends(require_analyst)])
def update_join(join_id: uuid.UUID, req: SemanticJoinCreate, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    try:
        return JoinService.update_join(db, user.tenant_id, join_id, user.email, **req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.post(
    "/joins/{join_id}/approve",
    response_model=SemanticJoinOut,
    dependencies=[Depends(require_analyst)],
    summary="Approve a join and trigger background embedding",
)
def approve_join(
    join_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    join = JoinService.approve_join(db, user.tenant_id, join_id, user.email)
    background_tasks.add_task(_embed_tenant, str(user.tenant_id))
    return join

@router.delete("/joins/{join_id}", dependencies=[Depends(require_analyst)])
def delete_join(join_id: uuid.UUID, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    join = JoinService.get_join(db, user.tenant_id, join_id)
    db.delete(join)
    db.commit()
    return {"status": "deleted"}


# --- Glossary ---

@router.post("/glossary", response_model=BusinessGlossaryOut, dependencies=[Depends(require_analyst)])
def create_term(
    req: BusinessGlossaryCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user)
):
    term = GlossaryService.create_term(db, user.tenant_id, user.email, **req.model_dump())
    background_tasks.add_task(_embed_tenant, str(user.tenant_id))
    return term

@router.get("/glossary", response_model=list[BusinessGlossaryOut])
def list_terms(db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return GlossaryService.list_terms(db, user.tenant_id)

@router.put("/glossary/{term_id}", response_model=BusinessGlossaryOut, dependencies=[Depends(require_analyst)])
def update_term(
    term_id: uuid.UUID,
    req: BusinessGlossaryCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user)
):
    term = GlossaryService.update_term(db, user.tenant_id, term_id, user.email, **req.model_dump())
    background_tasks.add_task(_embed_tenant, str(user.tenant_id))
    return term

@router.post(
    "/glossary/{term_id}/approve",
    response_model=BusinessGlossaryOut,
    dependencies=[Depends(require_analyst)],
    summary="Approve a glossary term and trigger background embedding",
)
def approve_glossary_term(
    term_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    term = GlossaryService.approve_term(db, user.tenant_id, term_id, user.email)
    background_tasks.add_task(_embed_tenant, str(user.tenant_id))
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

# ---------------------------------------------------------------------------
# Business Rules (Context Layer CDLC)
# ---------------------------------------------------------------------------

class BusinessRuleCreate(BaseModel):
    rule_title: str
    rule_instruction: str
    category: str = "filter_exclusion"  # 'filter_exclusion', 'fiscal_calendar', 'entity_mapping', 'calculation_quirk'
    keywords: str | None = None
    applies_to_tables: list[str] | None = None
    source_id: uuid.UUID | None = None


class BusinessRuleOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    source_id: uuid.UUID | None = None
    category: str
    rule_title: str
    rule_instruction: str
    keywords: str | None = None
    applies_to_tables: list[str] | None = None
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.post(
    "/rules",
    response_model=BusinessRuleOut,
    dependencies=[Depends(require_analyst)],
    summary="Add or update a Context Layer business rule",
)
@router.post(
    "/context/rules",
    response_model=BusinessRuleOut,
    dependencies=[Depends(require_analyst)],
    include_in_schema=False,
)
def create_or_update_business_rule(
    req: BusinessRuleCreate,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Create or update an institutional business rule with versioning."""
    rule = ContextLifecycleManager.add_or_update_rule(
        db=db,
        tenant_id=user.tenant_id,
        rule_title=req.rule_title,
        rule_instruction=req.rule_instruction,
        category=req.category,
        keywords=req.keywords,
        source_id=req.source_id,
    )
    if req.applies_to_tables is not None:
        rule.applies_to_tables = req.applies_to_tables
        db.commit()
        db.refresh(rule)
    return rule


@router.get(
    "/rules",
    response_model=list[BusinessRuleOut],
    dependencies=[Depends(get_current_user)],
    summary="List active Context Layer business rules",
)
@router.get(
    "/context/rules",
    response_model=list[BusinessRuleOut],
    dependencies=[Depends(get_current_user)],
    include_in_schema=False,
)
def list_business_rules(
    source_id: uuid.UUID | None = None,
    category: str | None = None,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """List all active business rules for the caller's tenant."""
    query = db.query(BusinessRule).filter(
        BusinessRule.tenant_id == user.tenant_id,
        BusinessRule.is_active == True,
    )
    if source_id:
        query = query.filter((BusinessRule.source_id == source_id) | (BusinessRule.source_id.is_(None)))
    if category:
        query = query.filter(BusinessRule.category == category)
    return query.order_by(BusinessRule.created_at.desc()).all()


@router.delete(
    "/rules/{rule_id}",
    dependencies=[Depends(require_analyst)],
    summary="Deactivate a business rule",
)
@router.delete(
    "/context/rules/{rule_id}",
    dependencies=[Depends(require_analyst)],
    include_in_schema=False,
)
def deactivate_business_rule(
    rule_id: uuid.UUID,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Soft-delete (deactivate) a business rule."""
    rule = (
        db.query(BusinessRule)
        .filter(
            BusinessRule.id == rule_id,
            BusinessRule.tenant_id == user.tenant_id,
        )
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Business rule not found")

    rule.is_active = False
    db.commit()
    return {"status": "deactivated", "rule_id": str(rule_id)}

# --- On-demand backfill (admin only) ---

@router.post(
    "/embed",
    dependencies=[Depends(require_admin)],
    summary="Re-embed all approved objects for the caller's tenant (backfill)",
)
def trigger_embedding(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
):
    """Enqueue a full re-embedding run for all approved semantic objects.

    Runs asynchronously in a FastAPI BackgroundTask — the endpoint returns
    immediately with 202 status. Useful for initial backfill or after bulk imports.
    """
    background_tasks.add_task(_embed_tenant, str(user.tenant_id))
    return {"status": "embedding_job_enqueued", "tenant_id": str(user.tenant_id)}


# ---------------------------------------------------------------------------
# Internal background helper
# ---------------------------------------------------------------------------

def _embed_tenant(tenant_id: str) -> None:
    """Background task: open a fresh DB session and run the embedding job.

    Uses a new session (not the request session which may already be closed)
    so this is safe to run after the HTTP response has been sent.
    """
    from app.db import session_scope
    from app.embeddings.job import embed_approved_objects

    with session_scope() as db:
        embed_approved_objects(tenant_id, db)
