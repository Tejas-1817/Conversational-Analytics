import re
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, or_, and_, desc
from sqlalchemy.orm import Session, selectinload

from app.api.deps import (
    get_current_user,
    verify_user_has_source_access,
    get_user_permitted_table_ids,
)
from app.audit import audit
from app.db import get_session
from app.models import (
    Dashboard,
    DashboardTab,
    DashboardWidget,
    SavedInsight,
    User,
    DataSource,
    TableMeta,
)
from app.chat_sql.sql_executor import SQLExecutor
from app.engine.dashboard_cache import DashboardResultCache
from app.ingestion.pii import column_is_sensitive, mask_value

import sqlglot
from sqlglot import exp


router = APIRouter(prefix="/dashboards", tags=["dashboards"])


# --- Schemas ---

class InsightCreate(BaseModel):
    name: str
    description: str | None = None
    query: str
    chart_type: str | None = "table"
    chart_config: dict | None = None
    source_id: uuid.UUID | None = None
    domain_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    message_id: uuid.UUID | None = None


class InsightUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    chart_type: str | None = None
    chart_config: dict | None = None


class InsightOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None = None
    query: str
    chart_type: str | None = "table"
    chart_config: dict | None = None
    source_id: uuid.UUID | None = None
    domain_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    message_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime | None = None
    last_run_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TabCreate(BaseModel):
    name: str


class TabUpdate(BaseModel):
    name: str


class TabReorder(BaseModel):
    tab_ids: list[uuid.UUID]


class TabOut(BaseModel):
    id: uuid.UUID
    dashboard_id: uuid.UUID
    name: str
    position: int
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class BulkSaveItem(BaseModel):
    name: str
    description: str | None = None
    query: str
    chart_type: str | None = "table"
    chart_config: dict | None = None
    source_id: uuid.UUID | None = None
    domain_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    message_id: uuid.UUID | None = None
    title_override: str | None = None
    chart_type_override: str | None = None
    settings: dict = Field(default_factory=dict)


class BulkSaveRequest(BaseModel):
    dashboard_id: uuid.UUID | None = None
    new_dashboard_name: str | None = None
    new_dashboard_description: str | None = None
    tab_id: uuid.UUID | None = None
    items: list[BulkSaveItem]


class BulkSaveResult(BaseModel):
    dashboard_id: uuid.UUID
    dashboard_name: str
    saved_count: int
    skipped_count: int
    widget_ids: list[uuid.UUID] = []
    insight_ids: list[uuid.UUID] = []
    skipped_duplicates: list[str] = []


class WidgetTabAction(BaseModel):
    target_tab_id: uuid.UUID | None = None


class WidgetCreate(BaseModel):
    insight_id: uuid.UUID | None = None
    tab_id: uuid.UUID | None = None
    widget_type: str = "insight"  # 'insight' | 'text'
    x: int = 0
    y: int | None = 0
    w: int = 6
    h: int = 4
    title_override: str | None = None
    chart_type_override: str | None = None
    settings: dict = Field(default_factory=dict)
    layouts: dict = Field(default_factory=dict)


class WidgetUpdate(BaseModel):
    title_override: str | None = None
    chart_type_override: str | None = None
    settings: dict | None = None


class WidgetLayoutItem(BaseModel):
    widget_id: uuid.UUID
    x: int
    y: int
    w: int
    h: int
    layouts: dict | None = None


class DashboardLayoutUpdate(BaseModel):
    widgets: list[WidgetLayoutItem]


class WidgetOut(BaseModel):
    id: uuid.UUID
    dashboard_id: uuid.UUID
    tab_id: uuid.UUID | None = None
    insight_id: uuid.UUID | None = None
    widget_type: str = "insight"
    insight: InsightOut | None = None
    x: int
    y: int
    w: int
    h: int
    title_override: str | None = None
    chart_type_override: str | None = None
    settings: dict = Field(default_factory=dict)
    layouts: dict = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class DashboardCreate(BaseModel):
    name: str
    description: str | None = None
    visibility: str = "private"  # 'private' | 'published'
    widgets: list[WidgetCreate] = []


class DashboardUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    visibility: str | None = None
    overview_summary: str | None = None


class DashboardOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None = None
    visibility: str = "published"
    overview_summary: str | None = None
    created_at: datetime
    updated_at: datetime
    tabs: list[TabOut] = []
    widgets: list[WidgetOut] = []

    model_config = ConfigDict(from_attributes=True)


class InsightRunResult(BaseModel):
    status: str  # 'success' | 'locked' | 'error'
    locked: bool = False
    detail: str | None = None
    error: str | None = None
    data: list[dict] = []
    columns: list[str] = []
    column_types: dict[str, str] = {}
    row_count: int = 0
    execution_time_ms: float = 0.0
    last_run_at: datetime | None = None
    cached: bool = False
    cached_at: datetime | None = None
    truncated: bool = False


# --- Helper functions ---

def validate_combo_layout_spec(spec: Any) -> bool:
    """
    Validates that a combo layout spec conforms to schema_version 1.
    Spec structure:
    {
        "schema_version": 1,
        "x_axis": str,
        "y_axes": [
            {
                "position": "left" | "right",
                "series_type": "bar" | "column" | "line" | "area",
                "columns": [str, ...],
                "unit": Optional[str]
            },
            ...
        ],
        "split_by": Optional[str]
    }
    """
    if not isinstance(spec, dict):
        return False
    if spec.get("schema_version") != 1:
        return False
    if not spec.get("x_axis") or not isinstance(spec["x_axis"], str):
        return False
    y_axes = spec.get("y_axes")
    if not isinstance(y_axes, list) or len(y_axes) == 0:
        return False
    valid_positions = {"left", "right"}
    valid_series = {"bar", "column", "line", "area"}
    for y_axis in y_axes:
        if not isinstance(y_axis, dict):
            return False
        if y_axis.get("position") not in valid_positions:
            return False
        if y_axis.get("series_type") not in valid_series:
            return False
        cols = y_axis.get("columns")
        if not isinstance(cols, list) or len(cols) == 0 or not all(isinstance(c, str) for c in cols):
            return False
    return True


def validate_safe_markdown_text(text: str) -> None:
    """
    Rejects raw HTML tags and unsafe link protocols (only http, https, mailto allowed).
    Raises HTTPException(422) on violation.
    """
    if not text:
        return
    # Detect HTML tags: e.g. <script>, <img ...>, <div>, </p>, etc.
    if re.search(r"<\s*([a-zA-Z][a-zA-Z0-9]*|/[a-zA-Z][a-zA-Z0-9]*)(\s+[^>]*)?>", text):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Raw HTML is not permitted in text content. Use Markdown formatting.",
        )
    # Detect unsafe markdown links: [text](protocol:...) where protocol is not http, https, mailto
    link_matches = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", text)
    for _, url in link_matches:
        clean_url = url.strip()
        if ":" in clean_url:
            proto = clean_url.split(":", 1)[0].lower().strip()
            if proto not in ("http", "https", "mailto"):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Unsafe link protocol '{proto}' is not permitted. Only http, https, and mailto are allowed.",
                )


def extract_tables_from_query(query: str, dialect: str = "postgres") -> set[str]:
    """Parse SQL query using sqlglot and return all referenced physical table names (lowercased)."""
    clean_sql = (query or "").strip()
    if not clean_sql:
        return set()

    sqlglot_dialects = {
        "postgresql": "postgres",
        "postgres": "postgres",
        "mysql": "mysql",
        "snowflake": "snowflake",
        "bigquery": "bigquery",
        "mssql": "tsql",
        "sqlite": "sqlite",
    }
    glot_dialect = sqlglot_dialects.get(dialect.lower(), "postgres")

    try:
        parsed = sqlglot.parse_one(clean_sql, read=glot_dialect)
    except Exception:
        try:
            parsed = sqlglot.parse_one(clean_sql)
        except Exception:
            return set()

    tables = set()
    cte_names = set()

    for cte in parsed.find_all(exp.CTE):
        if cte.alias_or_name:
            cte_names.add(cte.alias_or_name.lower())

    for table in parsed.find_all(exp.Table):
        tbl_name = table.name.lower() if table.name else ""
        if tbl_name and tbl_name not in cte_names:
            tables.add(tbl_name)

    return tables


def mask_result_rows(rows: list[dict], columns: list[str]) -> list[dict]:
    """Apply PII masking to query result rows before sending to client."""
    if not rows:
        return []
    masked_rows = []
    for row in rows:
        m_row = {}
        for col in columns:
            val = row.get(col)
            if val is None:
                m_row[col] = None
            elif column_is_sensitive(col):
                m_row[col] = "<masked: sensitive column>"
            elif isinstance(val, str):
                m_row[col] = mask_value(val)
            else:
                m_row[col] = val
        masked_rows.append(m_row)
    return masked_rows


def get_dashboard_or_404(dash_id: uuid.UUID, db: Session, user: User, require_write: bool = False) -> Dashboard:
    """Load dashboard with tenant isolation and authorization checks."""
    dash = db.scalar(
        select(Dashboard)
        .options(
            selectinload(Dashboard.tabs),
            selectinload(Dashboard.widgets).selectinload(DashboardWidget.insight),
        )
        .where(Dashboard.id == dash_id, Dashboard.tenant_id == user.tenant_id)
    )
    if not dash:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found")

    if require_write:
        if dash.user_id != user.id and user.role != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the dashboard owner or an administrator can modify this dashboard.",
            )
    else:
        # Read check: private dashboards are only visible to their owner and admin
        if dash.visibility == "private" and dash.user_id != user.id and user.role != "ADMIN":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dashboard not found")

    return dash


def verify_insight_read_access(insight: SavedInsight, db: Session, user: User) -> None:
    """Check if current user can view an insight."""
    if insight.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found")

    if insight.user_id == user.id or user.role == "ADMIN":
        return

    # Non-owner can read if insight is placed on a published dashboard or a dashboard user owns
    attached = db.scalar(
        select(DashboardWidget.id)
        .join(Dashboard, DashboardWidget.dashboard_id == Dashboard.id)
        .where(
            DashboardWidget.insight_id == insight.id,
            Dashboard.tenant_id == user.tenant_id,
            or_(Dashboard.visibility == "published", Dashboard.user_id == user.id),
        )
    )
    if not attached:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insight not found or access denied.",
        )


# --- Dashboard Endpoints ---

@router.get("", response_model=list[DashboardOut])
def list_dashboards(
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """List dashboards visible to the current user (own dashboards + published dashboards in tenant)."""
    query = (
        select(Dashboard)
        .options(
            selectinload(Dashboard.tabs),
            selectinload(Dashboard.widgets).selectinload(DashboardWidget.insight),
        )
        .where(Dashboard.tenant_id == user.tenant_id)
    )

    if user.role != "ADMIN":
        query = query.where(
            or_(
                Dashboard.user_id == user.id,
                Dashboard.visibility == "published",
            )
        )

    query = query.order_by(desc(Dashboard.updated_at))
    return db.scalars(query).all()


@router.post("", response_model=DashboardOut, status_code=status.HTTP_201_CREATED)
def create_dashboard(
    dash: DashboardCreate,
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Create a new dashboard. Default is empty and private to owner. VIEWER role cannot create."""
    if user.role == "VIEWER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Observers have read-only access and cannot create dashboards.",
        )

    visibility = (dash.visibility or "private").lower()
    if visibility not in ("private", "published"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Visibility must be 'private' or 'published'.",
        )

    # Check for duplicate dashboard name for this user in tenant
    existing = db.scalar(
        select(Dashboard).where(
            Dashboard.tenant_id == user.tenant_id,
            Dashboard.user_id == user.id,
            Dashboard.name == dash.name.strip(),
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A dashboard named '{dash.name.strip()}' already exists for your account.",
        )

    now = datetime.now(timezone.utc)
    db_obj = Dashboard(
        tenant_id=user.tenant_id,
        user_id=user.id,
        name=dash.name.strip(),
        description=dash.description.strip() if dash.description else None,
        visibility=visibility,
        created_at=now,
        updated_at=now,
    )
    db.add(db_obj)
    db.flush()

    for w in dash.widgets:
        db.add(
            DashboardWidget(
                dashboard_id=db_obj.id,
                insight_id=w.insight_id,
                x=w.x,
                y=w.y,
                w=w.w,
                h=w.h,
                title_override=w.title_override,
                chart_type_override=w.chart_type_override,
                settings=w.settings or {},
                layouts=w.layouts or {"lg": {"x": w.x, "y": w.y, "w": w.w, "h": w.h}},
            )
        )

    db.commit()

    audit(
        session=db,
        tenant_id=user.tenant_id,
        entity_type="dashboard",
        entity_id=db_obj.id,
        action="create_dashboard",
        actor=user.email,
        request=request,
    )
    db.commit()

    return get_dashboard_or_404(db_obj.id, db, user)

# --- Insight Endpoints ---

@router.get("/insights", response_model=list[InsightOut])
def list_insights(
    source_id: uuid.UUID | None = Query(None),
    conversation_id: uuid.UUID | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """List reusable insights in tenant accessible to current user."""
    query = select(SavedInsight).where(SavedInsight.tenant_id == user.tenant_id)

    if user.role != "ADMIN":
        # Owner + insights on published dashboards
        published_insight_ids = select(DashboardWidget.insight_id).join(
            Dashboard, DashboardWidget.dashboard_id == Dashboard.id
        ).where(
            Dashboard.tenant_id == user.tenant_id,
            Dashboard.visibility == "published",
        )
        query = query.where(
            or_(
                SavedInsight.user_id == user.id,
                SavedInsight.id.in_(published_insight_ids),
            )
        )

    if source_id:
        query = query.where(SavedInsight.source_id == source_id)
    if conversation_id:
        query = query.where(SavedInsight.conversation_id == conversation_id)
    if search:
        s = f"%{search.strip().lower()}%"
        query = query.where(or_(SavedInsight.name.ilike(s), SavedInsight.description.ilike(s)))

    query = query.order_by(desc(SavedInsight.created_at))
    return db.scalars(query).all()


@router.post("/insights", response_model=InsightOut, status_code=status.HTTP_201_CREATED)
def create_insight(
    insight: InsightCreate,
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Save an insight from chat or dashboard.
    Note: Automatic promotion to ApprovedSQLExample is intentionally REMOVED.
    Raw result rows are stripped/capped to ensure live data permission enforcement.
    """
    if user.role == "VIEWER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Observers have read-only access and cannot save insights.",
        )

    if insight.source_id:
        verify_user_has_source_access(db, user, insight.source_id)

    name = insight.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Insight name is required")

    # Check duplicate name for this user
    existing = db.scalar(
        select(SavedInsight).where(
            SavedInsight.tenant_id == user.tenant_id,
            SavedInsight.user_id == user.id,
            SavedInsight.name == name,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An insight named '{name}' already exists for your account.",
        )

    # Sanitize chart config: strip raw snapshot rows to enforce live querying and save storage
    sanitized_config = dict(insight.chart_config or {})
    if "data" in sanitized_config:
        # Keep empty or small preview only; live data is loaded via run endpoint
        sanitized_config["data"] = []

    now = datetime.now(timezone.utc)
    db_obj = SavedInsight(
        tenant_id=user.tenant_id,
        user_id=user.id,
        name=name,
        description=insight.description.strip() if insight.description else None,
        query=insight.query.strip(),
        chart_type=insight.chart_type or (insight.chart_config.get("chartType") if insight.chart_config else "table"),
        chart_config=sanitized_config,
        source_id=insight.source_id,
        domain_id=insight.domain_id,
        conversation_id=insight.conversation_id,
        message_id=insight.message_id,
        created_at=now,
        updated_at=now,
        last_run_at=now,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)

    audit(
        session=db,
        tenant_id=user.tenant_id,
        entity_type="saved_insight",
        entity_id=db_obj.id,
        action="create_insight",
        actor=user.email,
        request=request,
    )
    db.commit()

    return db_obj


@router.get("/insights/{insight_id}", response_model=InsightOut)
def get_insight(
    insight_id: uuid.UUID,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Get single insight details."""
    insight = db.scalar(
        select(SavedInsight).where(SavedInsight.id == insight_id, SavedInsight.tenant_id == user.tenant_id)
    )
    if not insight:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found")
    verify_insight_read_access(insight, db, user)
    return insight


@router.patch("/insights/{insight_id}", response_model=InsightOut)
def update_insight(
    insight_id: uuid.UUID,
    insight_update: InsightUpdate,
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Rename or edit an insight. Owner or Admin only."""
    insight = db.scalar(
        select(SavedInsight).where(SavedInsight.id == insight_id, SavedInsight.tenant_id == user.tenant_id)
    )
    if not insight:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found")

    if insight.user_id != user.id and user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the insight owner or an administrator can edit this insight.",
        )

    if insight_update.name is not None:
        new_name = insight_update.name.strip()
        if not new_name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name cannot be empty")
        existing = db.scalar(
            select(SavedInsight).where(
                SavedInsight.tenant_id == user.tenant_id,
                SavedInsight.user_id == insight.user_id,
                SavedInsight.name == new_name,
                SavedInsight.id != insight.id,
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"An insight named '{new_name}' already exists for your account.",
            )
        insight.name = new_name

    if insight_update.description is not None:
        insight.description = insight_update.description.strip() if insight_update.description else None

    if insight_update.chart_type is not None:
        insight.chart_type = insight_update.chart_type.strip()

    if insight_update.chart_config is not None:
        cfg = dict(insight_update.chart_config)
        cfg.pop("data", None)
        insight.chart_config = {**(insight.chart_config or {}), **cfg}

    insight.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(insight)

    audit(
        session=db,
        tenant_id=user.tenant_id,
        entity_type="saved_insight",
        entity_id=insight.id,
        action="update_insight",
        actor=user.email,
        request=request,
    )
    db.commit()

    return insight


@router.delete("/insights/{insight_id}")
def delete_insight(
    insight_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Delete an insight. Owner or Admin only.
    Blocked if the insight is actively in use on any dashboard.
    """
    insight = db.scalar(
        select(SavedInsight).where(SavedInsight.id == insight_id, SavedInsight.tenant_id == user.tenant_id)
    )
    if not insight:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found")

    if insight.user_id != user.id and user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the insight owner or an administrator can delete this insight.",
        )

    # Check if used on any dashboard
    used_dashboards = db.scalars(
        select(Dashboard.name)
        .join(DashboardWidget, Dashboard.id == DashboardWidget.dashboard_id)
        .where(DashboardWidget.insight_id == insight.id)
        .distinct()
    ).all()

    if used_dashboards:
        names_preview = ", ".join(f"'{n}'" for n in used_dashboards[:3])
        count = len(used_dashboards)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete insight '{insight.name}' because it is in use on "
                f"{count} dashboard{'s' if count > 1 else ''}: {names_preview}"
                f"{' and more' if count > 3 else ''}. Remove it from the dashboard(s) first."
            ),
        )

    audit(
        session=db,
        tenant_id=user.tenant_id,
        entity_type="saved_insight",
        entity_id=insight.id,
        action="delete_insight",
        actor=user.email,
        request=request,
    )

    db.delete(insight)
    db.commit()
    return {"ok": True, "detail": "Insight deleted successfully."}


# --- Insight Run Endpoint (Live Data & Permissions) ---

@router.post("/insights/{insight_id}/run", response_model=InsightRunResult)
@router.get("/insights/{insight_id}/run", response_model=InsightRunResult)
def run_insight(
    insight_id: uuid.UUID,
    force_refresh: bool = Query(False),
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Run an insight's SQL query dynamically with the current viewer's permissions.
    Enforces:
    1. Tenant isolation & dashboard viewer access.
    2. Data source access (verify_user_has_source_access).
    3. Permission-fingerprinted caching (bypassed on force_refresh=True).
    4. Table-level access (get_user_permitted_table_ids).
    5. SQL validation (read-only SELECT/WITH via sqlglot).
    6. 10,000-row execution limit with truncation detection.
    7. PII masking on returned data rows.
    Returns status='locked' with locked=True if the viewer lacks source or table permissions.
    """
    insight = db.scalar(
        select(SavedInsight).where(SavedInsight.id == insight_id, SavedInsight.tenant_id == user.tenant_id)
    )
    if not insight:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found")

    verify_insight_read_access(insight, db, user)

    if not insight.source_id:
        return InsightRunResult(
            status="error",
            error="This insight does not have an associated data source.",
        )

    # 1. Check viewer source access
    try:
        verify_user_has_source_access(db, user, insight.source_id)
    except HTTPException:
        return InsightRunResult(
            status="locked",
            locked=True,
            detail="You do not have permission to access the data source for this insight.",
        )

    source = db.scalar(
        select(DataSource).where(
            DataSource.id == insight.source_id,
            DataSource.tenant_id == user.tenant_id,
        )
    )
    if not source:
        return InsightRunResult(status="error", error="Configured data source not found.")

    clean_sql = (insight.query or "").strip()
    if not clean_sql.upper().startswith(("SELECT", "WITH")):
        return InsightRunResult(
            status="error",
            error="Only SELECT/WITH queries are allowed to be executed on dashboards.",
        )

    # 2. Check result cache (viewer-specific permission fingerprint)
    cache = DashboardResultCache.get_instance()
    perm_hash = cache.compute_permission_hash(user, insight.source_id, db)

    if not force_refresh:
        cached_res = cache.get(
            tenant_id=user.tenant_id,
            user_id=user.id,
            permission_hash=perm_hash,
            insight_id=insight.id,
            query_sql=clean_sql,
        )
        if cached_res:
            return InsightRunResult(**cached_res)

    # 3. Extract referenced tables and check viewer table permissions
    dialect = getattr(source, "type", "postgres") or "postgres"
    ref_tables = extract_tables_from_query(clean_sql, dialect=dialect)

    if ref_tables and user.role != "ADMIN":
        permitted_table_ids = get_user_permitted_table_ids(db, user, insight.source_id)
        table_metas = db.scalars(select(TableMeta).where(TableMeta.source_id == insight.source_id)).all()
        for tm in table_metas:
            if tm.table_name.lower() in ref_tables and tm.id not in permitted_table_ids:
                return InsightRunResult(
                    status="locked",
                    locked=True,
                    detail=f"You do not have permission to view table '{tm.table_name}' referenced in this insight.",
                )

    # 4. Execute query using read-only SQLExecutor capped at 10,000 rows
    limit_cap = 10_000
    try:
        (
            raw_data,
            row_count,
            exec_time_ms,
            columns,
            execution_error,
            result_truncated,
        ) = SQLExecutor.execute_query(
            sql=clean_sql,
            source=source,
            limit=limit_cap,
            timeout_ms=15_000,
        )
    except Exception as exc:
        return InsightRunResult(status="error", error=str(exc))

    if execution_error:
        return InsightRunResult(
            status="error",
            error=execution_error,
            execution_time_ms=exec_time_ms,
        )

    # 5. Apply PII masking to results
    masked_data = mask_result_rows(raw_data, columns)
    truncated = bool(result_truncated or row_count >= limit_cap or len(masked_data) >= limit_cap)

    now = datetime.now(timezone.utc)
    insight.last_run_at = now
    try:
        db.commit()
    except Exception:
        db.rollback()

    # Column type resolution
    column_types = {}
    if masked_data and len(masked_data) > 0:
        first_row = masked_data[0]
        for col in columns:
            val = first_row.get(col)
            if isinstance(val, (int, float)):
                column_types[col] = "number"
            elif isinstance(val, bool):
                column_types[col] = "boolean"
            else:
                column_types[col] = "string"

    result_payload = {
        "status": "success",
        "locked": False,
        "data": masked_data,
        "columns": columns,
        "column_types": column_types,
        "row_count": row_count,
        "execution_time_ms": exec_time_ms,
        "last_run_at": now.isoformat(),
        "cached": False,
        "cached_at": None,
        "truncated": truncated,
    }

    # Cache the result for this viewer
    cache.set(
        tenant_id=user.tenant_id,
        user_id=user.id,
        permission_hash=perm_hash,
        insight_id=insight.id,
        query_sql=clean_sql,
        payload=result_payload,
    )

    return InsightRunResult(
        status="success",
        locked=False,
        data=masked_data,
        columns=columns,
        column_types=column_types,
        row_count=row_count,
        execution_time_ms=exec_time_ms,
        last_run_at=now,
        cached=False,
        cached_at=None,
        truncated=truncated,
    )


@router.post("/bulk-save", response_model=BulkSaveResult, status_code=status.HTTP_201_CREATED)
def bulk_save_insights_to_dashboard(
    bulk_in: BulkSaveRequest,
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Add several answers from chat to a dashboard in a single transaction.
    Placement: free positions in chat order on current/first tab.
    Duplicate protection: skip items already attached to dashboard.
    """
    if user.role == "VIEWER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Observers have read-only access and cannot save insights.",
        )

    if not bulk_in.items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one item is required for bulk save.",
        )

    now = datetime.now(timezone.utc)
    target_dash: Dashboard

    if bulk_in.dashboard_id:
        target_dash = get_dashboard_or_404(bulk_in.dashboard_id, db, user, require_write=True)
    else:
        new_name = (bulk_in.new_dashboard_name or "").strip()
        if not new_name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Either dashboard_id or new_dashboard_name must be provided.",
            )
        existing = db.scalar(
            select(Dashboard).where(
                Dashboard.tenant_id == user.tenant_id,
                Dashboard.user_id == user.id,
                Dashboard.name == new_name,
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A dashboard named '{new_name}' already exists for your account.",
            )
        target_dash = Dashboard(
            tenant_id=user.tenant_id,
            user_id=user.id,
            name=new_name,
            description=bulk_in.new_dashboard_description.strip() if bulk_in.new_dashboard_description else None,
            visibility="published",
            created_at=now,
            updated_at=now,
        )
        db.add(target_dash)
        db.flush()

    # Determine target tab
    target_tab_id = bulk_in.tab_id
    if target_tab_id:
        if not any(t.id == target_tab_id for t in target_dash.tabs):
            target_tab_id = target_dash.tabs[0].id if target_dash.tabs else None
    elif target_dash.tabs:
        target_tab_id = target_dash.tabs[0].id

    # Existing query signatures for duplicate prevention
    existing_queries: set[str] = set()
    existing_message_ids: set[uuid.UUID] = set()
    for w in target_dash.widgets:
        if w.insight:
            if w.insight.query:
                existing_queries.add(w.insight.query.strip().lower())
            if w.insight.message_id:
                existing_message_ids.add(w.insight.message_id)

    # Coordinates calculation
    tab_widgets = [w for w in target_dash.widgets if w.tab_id == target_tab_id]
    curr_y = max([(w.y or 0) + (w.h or 4) for w in tab_widgets], default=0)
    curr_col = 0
    saved_count = 0
    skipped_count = 0
    skipped_duplicates: list[str] = []
    created_widget_ids: list[uuid.UUID] = []
    created_insight_ids: list[uuid.UUID] = []

    for item in bulk_in.items:
        clean_q = item.query.strip()
        if not clean_q or not clean_q.upper().startswith(("SELECT", "WITH")):
            skipped_count += 1
            continue

        if clean_q.lower() in existing_queries:
            skipped_count += 1
            skipped_duplicates.append(item.name.strip() or "Untitled Insight")
            continue
        if item.message_id and item.message_id in existing_message_ids:
            skipped_count += 1
            skipped_duplicates.append(item.name.strip() or "Untitled Insight")
            continue

        if item.source_id:
            try:
                verify_user_has_source_access(db, user, item.source_id)
            except Exception:
                skipped_count += 1
                continue

        insight_name = item.name.strip() or f"Insight {len(created_insight_ids) + 1}"
        existing_i = db.scalar(
            select(SavedInsight).where(
                SavedInsight.tenant_id == user.tenant_id,
                SavedInsight.user_id == user.id,
                SavedInsight.name == insight_name,
            )
        )
        if existing_i:
            insight_name = f"{insight_name} ({datetime.now().strftime('%H%M%S')})"

        sanitized_config = dict(item.chart_config or {})
        sanitized_config.pop("data", None)

        insight_obj = SavedInsight(
            id=uuid.uuid4(),
            tenant_id=user.tenant_id,
            user_id=user.id,
            name=insight_name,
            description=item.description.strip() if item.description else None,
            query=clean_q,
            chart_type=item.chart_type or (sanitized_config.get("chartType") if sanitized_config else "table"),
            chart_config=sanitized_config,
            source_id=item.source_id,
            domain_id=item.domain_id,
            conversation_id=item.conversation_id,
            message_id=item.message_id,
            created_at=now,
            updated_at=now,
            last_run_at=now,
        )
        db.add(insight_obj)
        db.flush()

        created_insight_ids.append(insight_obj.id)
        existing_queries.add(clean_q.lower())
        if item.message_id:
            existing_message_ids.add(item.message_id)

        w_width = 6
        w_height = 4
        w_x = curr_col * 6
        w_y = curr_y

        widget_obj = DashboardWidget(
            id=uuid.uuid4(),
            dashboard_id=target_dash.id,
            tab_id=target_tab_id,
            insight_id=insight_obj.id,
            widget_type="insight",
            x=w_x,
            y=w_y,
            w=w_width,
            h=w_height,
            title_override=item.title_override,
            chart_type_override=item.chart_type_override,
            settings=item.settings or {},
            layouts={"lg": {"x": w_x, "y": w_y, "w": w_width, "h": w_height}},
        )
        db.add(widget_obj)
        db.flush()

        created_widget_ids.append(widget_obj.id)
        saved_count += 1

        curr_col += 1
        if curr_col >= 2:
            curr_col = 0
            curr_y += w_height

    target_dash.updated_at = now
    db.commit()

    audit(
        session=db,
        tenant_id=user.tenant_id,
        entity_type="dashboard",
        entity_id=target_dash.id,
        action="bulk_save_insights",
        actor=user.email,
        request=request,
    )
    db.commit()

    return BulkSaveResult(
        dashboard_id=target_dash.id,
        dashboard_name=target_dash.name,
        saved_count=saved_count,
        skipped_count=skipped_count,
        widget_ids=created_widget_ids,
        insight_ids=created_insight_ids,
        skipped_duplicates=skipped_duplicates,
    )


# --- Single Dashboard & Widget Endpoints ---

@router.get("/{dash_id}", response_model=DashboardOut)
def get_dashboard(
    dash_id: uuid.UUID,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Get single dashboard details with widgets and insights."""
    return get_dashboard_or_404(dash_id, db, user, require_write=False)


@router.patch("/{dash_id}", response_model=DashboardOut)
def update_dashboard_metadata(
    dash_id: uuid.UUID,
    dash_update: DashboardUpdate,
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Rename dashboard, edit description, or change visibility. Owner or Admin only."""
    dash = get_dashboard_or_404(dash_id, db, user, require_write=True)

    if dash_update.name is not None:
        new_name = dash_update.name.strip()
        if not new_name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name cannot be empty")
        # Check duplicate name for this owner
        existing = db.scalar(
            select(Dashboard).where(
                Dashboard.tenant_id == user.tenant_id,
                Dashboard.user_id == dash.user_id,
                Dashboard.name == new_name,
                Dashboard.id != dash.id,
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A dashboard named '{new_name}' already exists for your account.",
            )
        dash.name = new_name

    if dash_update.description is not None:
        dash.description = dash_update.description.strip() if dash_update.description else None

    if dash_update.visibility is not None:
        new_vis = dash_update.visibility.lower()
        if new_vis not in ("private", "published"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Visibility must be 'private' or 'published'.",
            )
        dash.visibility = new_vis

    if dash_update.overview_summary is not None:
        raw_overview = dash_update.overview_summary.strip() if dash_update.overview_summary else None
        if raw_overview:
            if len(raw_overview) > 10_000:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Overview summary exceeds maximum limit of 10,000 characters.",
                )
            validate_safe_markdown_text(raw_overview)
        dash.overview_summary = raw_overview

    dash.updated_at = datetime.now(timezone.utc)
    db.commit()

    audit(
        session=db,
        tenant_id=user.tenant_id,
        entity_type="dashboard",
        entity_id=dash.id,
        action="update_dashboard",
        actor=user.email,
        request=request,
    )
    db.commit()

    return get_dashboard_or_404(dash.id, db, user)


@router.delete("/{dash_id}")
def delete_dashboard(
    dash_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Delete a dashboard. Owner or Admin only."""
    dash = get_dashboard_or_404(dash_id, db, user, require_write=True)

    audit(
        session=db,
        tenant_id=user.tenant_id,
        entity_type="dashboard",
        entity_id=dash.id,
        action="delete_dashboard",
        actor=user.email,
        request=request,
    )

    db.delete(dash)
    db.commit()
    return {"ok": True, "detail": "Dashboard deleted successfully."}


# --- Widget Endpoints ---

@router.put("/{dash_id}/layout", response_model=DashboardOut)
def update_dashboard_layout(
    dash_id: uuid.UUID,
    layout_update: DashboardLayoutUpdate,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Update widget positions in-place without deleting and recreating widgets.
    Preserves widget IDs and handles responsive breakpoint layouts.
    """
    dash = get_dashboard_or_404(dash_id, db, user, require_write=True)

    # Fetch existing widgets for this dashboard
    existing_widgets = {
        w.id: w for w in db.scalars(select(DashboardWidget).where(DashboardWidget.dashboard_id == dash.id)).all()
    }

    for item in layout_update.widgets:
        widget = existing_widgets.get(item.widget_id)
        if widget:
            widget.x = item.x
            widget.y = item.y
            widget.w = item.w
            widget.h = item.h
            if item.layouts:
                widget.layouts = {**(widget.layouts or {}), **item.layouts}
            else:
                current_layouts = dict(widget.layouts or {})
                current_layouts["lg"] = {"x": item.x, "y": item.y, "w": item.w, "h": item.h}
                widget.layouts = current_layouts

    dash.updated_at = datetime.now(timezone.utc)
    db.commit()

    return get_dashboard_or_404(dash.id, db, user)


@router.post("/{dash_id}/widgets", response_model=WidgetOut, status_code=status.HTTP_201_CREATED)
def add_widget_to_dashboard(
    dash_id: uuid.UUID,
    widget_in: WidgetCreate,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Add a widget (insight or text) to the dashboard. Owner or Admin only."""
    dash = get_dashboard_or_404(dash_id, db, user, require_write=True)

    insight = None
    widget_type = (widget_in.widget_type or "insight").lower()

    if widget_type == "text":
        txt = (widget_in.settings or {}).get("text") or (widget_in.settings or {}).get("content") or ""
        validate_safe_markdown_text(txt)
    else:
        if not widget_in.insight_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="insight_id is required for insight widgets.",
            )
        insight = db.scalar(
            select(SavedInsight).where(
                SavedInsight.id == widget_in.insight_id,
                SavedInsight.tenant_id == user.tenant_id,
            )
        )
        if not insight:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found")

    target_tab_id = widget_in.tab_id
    if target_tab_id:
        if not any(t.id == target_tab_id for t in dash.tabs):
            target_tab_id = dash.tabs[0].id if dash.tabs else None
    elif dash.tabs:
        target_tab_id = dash.tabs[0].id

    tab_widgets = [w for w in dash.widgets if w.tab_id == target_tab_id]
    w_y = widget_in.y if widget_in.y is not None else 0
    if widget_in.y is None or widget_in.y < 0:
        w_y = max([w.y + w.h for w in tab_widgets], default=0)

    layouts = widget_in.layouts or {"lg": {"x": widget_in.x, "y": w_y, "w": widget_in.w, "h": widget_in.h}}
    widget = DashboardWidget(
        dashboard_id=dash.id,
        tab_id=target_tab_id,
        insight_id=insight.id if insight else None,
        widget_type=widget_type,
        x=widget_in.x,
        y=w_y,
        w=widget_in.w,
        h=widget_in.h,
        title_override=widget_in.title_override,
        chart_type_override=widget_in.chart_type_override,
        settings=widget_in.settings or {},
        layouts=layouts,
    )
    db.add(widget)
    dash.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(widget)
    widget.insight = insight
    return widget


@router.patch("/{dash_id}/widgets/{widget_id}", response_model=WidgetOut)
def update_widget(
    dash_id: uuid.UUID,
    widget_id: uuid.UUID,
    widget_in: WidgetUpdate,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Update widget customization settings (title override, chart type override)."""
    dash = get_dashboard_or_404(dash_id, db, user, require_write=True)

    widget = db.scalar(
        select(DashboardWidget)
        .options(selectinload(DashboardWidget.insight))
        .where(DashboardWidget.id == widget_id, DashboardWidget.dashboard_id == dash.id)
    )
    if not widget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")

    if widget_in.title_override is not None:
        widget.title_override = widget_in.title_override.strip() if widget_in.title_override else None

    if widget_in.chart_type_override is not None:
        widget.chart_type_override = widget_in.chart_type_override.strip() if widget_in.chart_type_override else None

    if widget_in.settings is not None:
        txt = widget_in.settings.get("text") or widget_in.settings.get("content")
        if txt:
            validate_safe_markdown_text(txt)
        if "combo_spec" in widget_in.settings and widget_in.settings["combo_spec"] is not None:
            if not validate_combo_layout_spec(widget_in.settings["combo_spec"]):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Invalid combo chart layout spec.",
                )
        widget.settings = {**(widget.settings or {}), **widget_in.settings}

    dash.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(widget)
    return widget


@router.delete("/{dash_id}/widgets/{widget_id}")
def remove_widget_from_dashboard(
    dash_id: uuid.UUID,
    widget_id: uuid.UUID,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Remove a widget from a dashboard. Does NOT delete the underlying insight."""
    dash = get_dashboard_or_404(dash_id, db, user, require_write=True)

    widget = db.scalar(
        select(DashboardWidget).where(DashboardWidget.id == widget_id, DashboardWidget.dashboard_id == dash.id)
    )
    if not widget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")

    db.delete(widget)
    dash.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "detail": "Widget removed from dashboard."}


@router.post("/{dash_id}/widgets/{widget_id}/duplicate", response_model=WidgetOut, status_code=status.HTTP_201_CREATED)
def duplicate_widget(
    dash_id: uuid.UUID,
    widget_id: uuid.UUID,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Duplicate an existing widget on the same dashboard."""
    dash = get_dashboard_or_404(dash_id, db, user, require_write=True)

    original = db.scalar(
        select(DashboardWidget)
        .options(selectinload(DashboardWidget.insight))
        .where(DashboardWidget.id == widget_id, DashboardWidget.dashboard_id == dash.id)
    )
    if not original:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")

    tab_widgets = [w for w in dash.widgets if w.tab_id == original.tab_id]
    new_y = max([w.y + w.h for w in tab_widgets], default=0)
    new_layouts = dict(original.layouts or {})
    if "lg" in new_layouts:
        new_layouts["lg"] = {**new_layouts["lg"], "y": new_y}

    dup = DashboardWidget(
        dashboard_id=dash.id,
        tab_id=original.tab_id,
        insight_id=original.insight_id,
        widget_type=original.widget_type,
        x=original.x,
        y=new_y,
        w=original.w,
        h=original.h,
        title_override=f"{original.title_override} (Copy)" if original.title_override else None,
        chart_type_override=original.chart_type_override,
        settings=dict(original.settings or {}),
        layouts=new_layouts,
    )
    db.add(dup)
    dash.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(dup)
    dup.insight = original.insight
    return dup


@router.post("/{dash_id}/widgets/{widget_id}/move", response_model=WidgetOut)
def move_widget_to_tab(
    dash_id: uuid.UUID,
    widget_id: uuid.UUID,
    action: WidgetTabAction,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Move a widget to a specific tab on the dashboard."""
    dash = get_dashboard_or_404(dash_id, db, user, require_write=True)
    widget = db.scalar(
        select(DashboardWidget)
        .options(selectinload(DashboardWidget.insight))
        .where(DashboardWidget.id == widget_id, DashboardWidget.dashboard_id == dash.id)
    )
    if not widget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")

    if action.target_tab_id:
        if not any(t.id == action.target_tab_id for t in dash.tabs):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target tab does not exist.")

    target_widgets = [w for w in dash.widgets if w.tab_id == action.target_tab_id and w.id != widget.id]
    new_y = max([w.y + w.h for w in target_widgets], default=0)

    widget.tab_id = action.target_tab_id
    widget.x = 0
    widget.y = new_y
    if widget.layouts and "lg" in widget.layouts:
        widget.layouts["lg"] = {**widget.layouts["lg"], "x": 0, "y": new_y}

    dash.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(widget)
    return widget


@router.post("/{dash_id}/widgets/{widget_id}/clone", response_model=WidgetOut, status_code=status.HTTP_201_CREATED)
def clone_widget_to_tab(
    dash_id: uuid.UUID,
    widget_id: uuid.UUID,
    action: WidgetTabAction,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Clone a widget to a specific tab on the dashboard."""
    dash = get_dashboard_or_404(dash_id, db, user, require_write=True)
    original = db.scalar(
        select(DashboardWidget)
        .options(selectinload(DashboardWidget.insight))
        .where(DashboardWidget.id == widget_id, DashboardWidget.dashboard_id == dash.id)
    )
    if not original:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")

    target_tab_id = action.target_tab_id if action.target_tab_id is not None else original.tab_id
    if target_tab_id and not any(t.id == target_tab_id for t in dash.tabs):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target tab does not exist.")

    target_widgets = [w for w in dash.widgets if w.tab_id == target_tab_id]
    new_y = max([w.y + w.h for w in target_widgets], default=0)

    new_layouts = dict(original.layouts or {})
    new_layouts["lg"] = {"x": original.x, "y": new_y, "w": original.w, "h": original.h}

    clone = DashboardWidget(
        dashboard_id=dash.id,
        tab_id=target_tab_id,
        insight_id=original.insight_id,
        widget_type=original.widget_type,
        x=original.x,
        y=new_y,
        w=original.w,
        h=original.h,
        title_override=f"{original.title_override} (Copy)" if original.title_override else None,
        chart_type_override=original.chart_type_override,
        settings=dict(original.settings or {}),
        layouts=new_layouts,
    )
    db.add(clone)
    dash.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(clone)
    clone.insight = original.insight
    return clone


# --- Tab Endpoints ---

@router.post("/{dash_id}/tabs", response_model=DashboardOut, status_code=status.HTTP_201_CREATED)
def create_dashboard_tab(
    dash_id: uuid.UUID,
    tab_in: TabCreate,
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Create a tab on the dashboard.
    When first tab is added, existing widgets are automatically migrated to a 'Main' tab.
    """
    dash = get_dashboard_or_404(dash_id, db, user, require_write=True)
    name = tab_in.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tab name is required.")

    now = datetime.now(timezone.utc)

    if len(dash.tabs) == 0:
        main_tab = DashboardTab(
            dashboard_id=dash.id,
            name="Main",
            position=0,
            created_at=now,
            updated_at=now,
        )
        db.add(main_tab)
        dash.tabs.append(main_tab)
        db.flush()

        for w in dash.widgets:
            w.tab_id = main_tab.id

        new_tab = DashboardTab(
            dashboard_id=dash.id,
            name=name,
            position=1,
            created_at=now,
            updated_at=now,
        )
        db.add(new_tab)
        dash.tabs.append(new_tab)
    else:
        if any(t.name.lower() == name.lower() for t in dash.tabs):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A tab named '{name}' already exists on this dashboard.",
            )
        next_pos = max((t.position for t in dash.tabs), default=-1) + 1
        new_tab = DashboardTab(
            dashboard_id=dash.id,
            name=name,
            position=next_pos,
            created_at=now,
            updated_at=now,
        )
        db.add(new_tab)
        dash.tabs.append(new_tab)

    dash.updated_at = now
    db.commit()

    audit(
        session=db,
        tenant_id=user.tenant_id,
        entity_type="dashboard_tab",
        entity_id=dash.id,
        action="create_tab",
        actor=user.email,
        request=request,
    )
    db.commit()

    return get_dashboard_or_404(dash.id, db, user)


@router.patch("/{dash_id}/tabs/{tab_id}", response_model=DashboardOut)
def update_dashboard_tab(
    dash_id: uuid.UUID,
    tab_id: uuid.UUID,
    tab_in: TabUpdate,
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Rename a dashboard tab. Owner or Admin only."""
    dash = get_dashboard_or_404(dash_id, db, user, require_write=True)
    target_tab = next((t for t in dash.tabs if t.id == tab_id), None)
    if not target_tab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tab not found.")

    new_name = tab_in.name.strip()
    if not new_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tab name is required.")

    if any(t.id != tab_id and t.name.lower() == new_name.lower() for t in dash.tabs):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A tab named '{new_name}' already exists on this dashboard.",
        )

    target_tab.name = new_name
    target_tab.updated_at = datetime.now(timezone.utc)
    dash.updated_at = datetime.now(timezone.utc)
    db.commit()

    audit(
        session=db,
        tenant_id=user.tenant_id,
        entity_type="dashboard_tab",
        entity_id=target_tab.id,
        action="rename_tab",
        actor=user.email,
        request=request,
    )
    db.commit()

    return get_dashboard_or_404(dash.id, db, user)


@router.put("/{dash_id}/tabs/reorder", response_model=DashboardOut)
def reorder_dashboard_tabs(
    dash_id: uuid.UUID,
    reorder_in: TabReorder,
    request: Request,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Reorder dashboard tabs."""
    dash = get_dashboard_or_404(dash_id, db, user, require_write=True)
    tab_map = {t.id: t for t in dash.tabs}

    for pos, tid in enumerate(reorder_in.tab_ids):
        if tid in tab_map:
            tab_map[tid].position = pos

    dash.updated_at = datetime.now(timezone.utc)
    db.commit()

    audit(
        session=db,
        tenant_id=user.tenant_id,
        entity_type="dashboard_tab",
        entity_id=dash.id,
        action="reorder_tabs",
        actor=user.email,
        request=request,
    )
    db.commit()

    return get_dashboard_or_404(dash.id, db, user)


@router.delete("/{dash_id}/tabs/{tab_id}", response_model=DashboardOut)
def delete_dashboard_tab(
    dash_id: uuid.UUID,
    tab_id: uuid.UUID,
    move_to_tab_id: uuid.UUID | None = Query(None),
    request: Request = None,
    db: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Delete a dashboard tab.
    Requires at least one tab to remain.
    Optionally moves widgets to another tab.
    """
    dash = get_dashboard_or_404(dash_id, db, user, require_write=True)
    if len(dash.tabs) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A dashboard must keep at least one tab.",
        )

    target_tab = next((t for t in dash.tabs if t.id == tab_id), None)
    if not target_tab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tab not found.")

    if move_to_tab_id:
        if move_to_tab_id == tab_id or not any(t.id == move_to_tab_id for t in dash.tabs):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid target tab specified to move widgets.",
            )
        target_widgets = [w for w in dash.widgets if w.tab_id == move_to_tab_id]
        curr_y = max([w.y + w.h for w in target_widgets], default=0)
        for w in dash.widgets:
            if w.tab_id == tab_id:
                w.tab_id = move_to_tab_id
                w.y = curr_y
                if w.layouts and "lg" in w.layouts:
                    w.layouts["lg"]["y"] = curr_y
                curr_y += w.h
    else:
        for w in list(dash.widgets):
            if w.tab_id == tab_id:
                db.delete(w)

    db.delete(target_tab)
    db.flush()

    # Reindex remaining tabs
    remaining_tabs = sorted([t for t in dash.tabs if t.id != tab_id], key=lambda t: t.position)
    for idx, t in enumerate(remaining_tabs):
        t.position = idx

    dash.updated_at = datetime.now(timezone.utc)
    db.commit()

    audit(
        session=db,
        tenant_id=user.tenant_id,
        entity_type="dashboard_tab",
        entity_id=tab_id,
        action="delete_tab",
        actor=user.email,
        request=request,
    )
    db.commit()

    return get_dashboard_or_404(dash.id, db, user)
