import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db import get_session
from app.api.deps import get_current_user
from app.models import User, Dashboard, DashboardWidget, SavedInsight
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/dashboards", tags=["dashboards"])

# --- Schemas ---

class InsightCreate(BaseModel):
    name: str
    description: Optional[str] = None
    query: str
    chart_config: Optional[dict] = None

class InsightOut(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    query: str
    chart_config: Optional[dict] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class WidgetCreate(BaseModel):
    insight_id: uuid.UUID
    x: int
    y: int
    w: int
    h: int

class WidgetOut(BaseModel):
    id: uuid.UUID
    insight: InsightOut
    x: int
    y: int
    w: int
    h: int

    class Config:
        from_attributes = True

class DashboardCreate(BaseModel):
    name: str
    description: Optional[str] = None
    widgets: List[WidgetCreate] = []

class DashboardOut(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    created_at: datetime
    widgets: List[WidgetOut] = []

    class Config:
        from_attributes = True

# --- Endpoints ---

@router.post("/insights", response_model=InsightOut)
def create_insight(insight: InsightCreate, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    db_obj = SavedInsight(
        tenant_id=user.tenant_id,
        user_id=user.id,
        name=insight.name,
        description=insight.description,
        query=insight.query,
        chart_config=insight.chart_config
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj

@router.get("/insights", response_model=List[InsightOut])
def get_insights(db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return db.scalars(select(SavedInsight).where(SavedInsight.tenant_id == user.tenant_id)).all()

@router.post("/", response_model=DashboardOut)
def create_dashboard(dash: DashboardCreate, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    db_obj = Dashboard(
        tenant_id=user.tenant_id,
        user_id=user.id,
        name=dash.name,
        description=dash.description
    )
    db.add(db_obj)
    db.commit()
    
    for w in dash.widgets:
        db.add(DashboardWidget(
            dashboard_id=db_obj.id,
            insight_id=w.insight_id,
            x=w.x, y=w.y, w=w.w, h=w.h
        ))
    db.commit()
    db.refresh(db_obj)
    return db_obj

@router.get("/", response_model=List[DashboardOut])
def get_dashboards(db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    return db.scalars(select(Dashboard).where(Dashboard.tenant_id == user.tenant_id)).all()

@router.get("/{dash_id}", response_model=DashboardOut)
def get_dashboard(dash_id: uuid.UUID, db: Session = Depends(get_session), user: User = Depends(get_current_user)):
    dash = db.scalar(select(Dashboard).where(Dashboard.id == dash_id, Dashboard.tenant_id == user.tenant_id))
    if not dash:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return dash
