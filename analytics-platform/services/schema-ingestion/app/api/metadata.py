"""Browse and review captured metadata. Every review action is audited."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_api_key
from app.audit import record
from app.db import get_session
from app.models import ColumnMeta, DataSource, Relationship, TableMeta
from app.schemas import ColumnOut, RelationshipOut, ReviewRequest, TableOut

router = APIRouter(prefix="/metadata", tags=["metadata"], dependencies=[Depends(require_api_key)])

_ACTION_TO_STATUS = {"approve": "approved", "reject": "rejected",
                     "needs_clarification": "needs_clarification", "edit": "reviewed"}


@router.get("/sources/{source_id}/tables", response_model=list[TableOut])
def list_tables(source_id: uuid.UUID, session: Session = Depends(get_session)) -> list[TableMeta]:
    return (session.query(TableMeta).filter_by(source_id=source_id)
            .order_by(TableMeta.schema_name, TableMeta.table_name).all())


@router.get("/tables/{table_id}/columns", response_model=list[ColumnOut])
def list_columns(table_id: uuid.UUID, session: Session = Depends(get_session)) -> list[ColumnMeta]:
    return (session.query(ColumnMeta).filter_by(table_id=table_id)
            .order_by(ColumnMeta.ordinal_position).all())


@router.get("/sources/{source_id}/relationships", response_model=list[RelationshipOut])
def list_relationships(source_id: uuid.UUID, session: Session = Depends(get_session)) -> list[Relationship]:
    return (session.query(Relationship)
            .join(ColumnMeta, Relationship.from_column_id == ColumnMeta.id)
            .join(TableMeta, ColumnMeta.table_id == TableMeta.id)
            .filter(TableMeta.source_id == source_id)
            .order_by(Relationship.confidence.desc()).all())


def _tenant_of(session: Session, table: TableMeta) -> uuid.UUID | None:
    source = session.get(DataSource, table.source_id)
    return source.tenant_id if source else None


@router.post("/tables/{table_id}/review", response_model=TableOut)
def review_table(table_id: uuid.UUID, req: ReviewRequest,
                 session: Session = Depends(get_session)) -> TableMeta:
    table = session.get(TableMeta, table_id)
    if table is None:
        raise HTTPException(status_code=404, detail="Table not found")
    before = {"status": table.status, "business_name": table.business_name,
              "description": table.description, "grain": table.grain}

    for field in ("business_name", "description", "grain"):
        value = getattr(req, field)
        if value is not None:
            setattr(table, field, value)
    table.status = _ACTION_TO_STATUS[req.action]
    table.updated_by = req.actor

    record(session, tenant_id=_tenant_of(session, table), entity_type="tables_meta",
           entity_id=table.id, action=req.action, actor=req.actor, before=before,
           after={"status": table.status, "business_name": table.business_name,
                  "description": table.description, "grain": table.grain})
    return table


@router.post("/columns/{column_id}/review", response_model=ColumnOut)
def review_column(column_id: uuid.UUID, req: ReviewRequest,
                  session: Session = Depends(get_session)) -> ColumnMeta:
    column = session.get(ColumnMeta, column_id)
    if column is None:
        raise HTTPException(status_code=404, detail="Column not found")
    before = {"status": column.status, "business_name": column.business_name,
              "description": column.description, "role": column.role,
              "aggregation": column.aggregation, "additivity": column.additivity,
              "synonyms": column.synonyms}

    for field in ("business_name", "description", "synonyms", "role", "aggregation", "additivity"):
        value = getattr(req, field)
        if value is not None:
            setattr(column, field, value)
    column.status = _ACTION_TO_STATUS[req.action]
    column.updated_by = req.actor

    table = session.get(TableMeta, column.table_id)
    record(session, tenant_id=_tenant_of(session, table) if table else None,
           entity_type="columns_meta", entity_id=column.id, action=req.action, actor=req.actor,
           before=before,
           after={"status": column.status, "business_name": column.business_name,
                  "description": column.description, "role": column.role,
                  "aggregation": column.aggregation, "additivity": column.additivity,
                  "synonyms": column.synonyms})
    return column


@router.post("/relationships/{relationship_id}/review", response_model=RelationshipOut)
def review_relationship(relationship_id: uuid.UUID, req: ReviewRequest,
                        session: Session = Depends(get_session)) -> Relationship:
    rel = session.get(Relationship, relationship_id)
    if rel is None:
        raise HTTPException(status_code=404, detail="Relationship not found")
    before = {"status": rel.status, "cardinality": rel.cardinality}

    if req.cardinality is not None:
        rel.cardinality = req.cardinality
    rel.status = _ACTION_TO_STATUS[req.action]
    rel.updated_by = req.actor

    from_col = session.get(ColumnMeta, rel.from_column_id)
    table = session.get(TableMeta, from_col.table_id) if from_col else None
    record(session, tenant_id=_tenant_of(session, table) if table else None,
           entity_type="relationships", entity_id=rel.id, action=req.action, actor=req.actor,
           before=before, after={"status": rel.status, "cardinality": rel.cardinality})
    return rel
