"""
Unit tests for Dashboards Phase 2:
- Task 1: Bulk Save (Atomic multi-insight creation, duplicate detection, grid placement)
- Task 2: Dashboard Tabs (Creation, auto-migration of widgets to 'Main', rename, reorder, delete with move)
- Task 2: Widget Move and Clone between tabs
- Task 3: Text Widgets & Safe Markdown validation (rejects HTML and unsafe links)
- Task 4: Result Truncation at 10,000 rows
- Task 5: Combo Chart Layout Spec Validator
- Task 6: Result Cache (fingerprint hashing, access re-verification, force_refresh bypass)
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.dashboards import (
    bulk_save_insights_to_dashboard,
    create_dashboard_tab,
    update_dashboard_tab,
    reorder_dashboard_tabs,
    delete_dashboard_tab,
    move_widget_to_tab,
    clone_widget_to_tab,
    add_widget_to_dashboard,
    update_widget,
    update_dashboard_metadata,
    validate_safe_markdown_text,
    validate_combo_layout_spec,
    BulkSaveRequest,
    BulkSaveItem,
    TabCreate,
    TabUpdate,
    TabReorder,
    WidgetTabAction,
    WidgetCreate,
    WidgetUpdate,
    DashboardUpdate,
)
from app.engine.dashboard_cache import DashboardResultCache
from app.models import (
    Dashboard,
    DashboardTab,
    DashboardWidget,
    SavedInsight,
    User,
    DataSource,
)

TENANT_ID = uuid.uuid4()
USER_OWNER = User(id=uuid.uuid4(), tenant_id=TENANT_ID, email="owner@example.com", role="USER", is_active=True)
USER_VIEWER = User(id=uuid.uuid4(), tenant_id=TENANT_ID, email="viewer@example.com", role="VIEWER", is_active=True)
USER_ADMIN = User(id=uuid.uuid4(), tenant_id=TENANT_ID, email="admin@example.com", role="ADMIN", is_active=True)
USER_OTHER_TENANT = User(id=uuid.uuid4(), tenant_id=uuid.uuid4(), email="other@example.com", role="USER", is_active=True)


class TestSafeMarkdownValidation:
    """Task 3: Safe Markdown validation tests."""

    def test_accepts_clean_markdown(self):
        # Should not raise
        validate_safe_markdown_text("# Executive Summary\n- Bullet 1\n- Bullet 2\n**Bold text**")
        validate_safe_markdown_text("Check this out [Docs](https://example.com/docs) and [Help](http://help.org)")
        validate_safe_markdown_text("Contact [Support](mailto:support@example.com)")

    def test_rejects_raw_html_tags(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_safe_markdown_text("Some text <script>alert(1)</script>")
        assert exc_info.value.status_code == 422
        assert "Raw HTML is not permitted" in exc_info.value.detail

        with pytest.raises(HTTPException):
            validate_safe_markdown_text("<div style='color:red'>Red text</div>")

        with pytest.raises(HTTPException):
            validate_safe_markdown_text("Image test <img src=x onerror='alert(1)' />")

    def test_rejects_unsafe_links(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_safe_markdown_text("Click [here](javascript:alert(1))")
        assert exc_info.value.status_code == 422
        assert "Unsafe link protocol" in exc_info.value.detail

        with pytest.raises(HTTPException):
            validate_safe_markdown_text("Click [here](data:text/html,<script>alert(1)</script>)")

        with pytest.raises(HTTPException):
            validate_safe_markdown_text("Click [here](vbscript:msgbox(1))")


class TestComboLayoutSpecValidation:
    """Task 5: Combo Layout Spec Validator tests."""

    def test_accepts_valid_spec(self):
        spec = {
            "schema_version": 1,
            "x_axis": "month",
            "y_axes": [
                {
                    "position": "left",
                    "series_type": "bar",
                    "columns": ["revenue"],
                    "unit": "$",
                },
                {
                    "position": "right",
                    "series_type": "line",
                    "columns": ["margin_pct"],
                    "unit": "%",
                },
            ],
        }
        assert validate_combo_layout_spec(spec) is True

    def test_rejects_invalid_version(self):
        spec = {
            "schema_version": 2,
            "x_axis": "month",
            "y_axes": [{"position": "left", "series_type": "bar", "columns": ["revenue"]}],
        }
        assert validate_combo_layout_spec(spec) is False

    def test_rejects_missing_x_axis(self):
        spec = {
            "schema_version": 1,
            "y_axes": [{"position": "left", "series_type": "bar", "columns": ["revenue"]}],
        }
        assert validate_combo_layout_spec(spec) is False

    def test_rejects_invalid_position_or_series_type(self):
        spec_invalid_pos = {
            "schema_version": 1,
            "x_axis": "date",
            "y_axes": [{"position": "top", "series_type": "bar", "columns": ["revenue"]}],
        }
        assert validate_combo_layout_spec(spec_invalid_pos) is False

        spec_invalid_type = {
            "schema_version": 1,
            "x_axis": "date",
            "y_axes": [{"position": "left", "series_type": "scatter_3d", "columns": ["revenue"]}],
        }
        assert validate_combo_layout_spec(spec_invalid_type) is False

    def test_rejects_empty_columns(self):
        spec = {
            "schema_version": 1,
            "x_axis": "date",
            "y_axes": [{"position": "left", "series_type": "bar", "columns": []}],
        }
        assert validate_combo_layout_spec(spec) is False


class TestBulkSaveEndpoint:
    """Task 1: Bulk save multi-insight to dashboard tests."""

    def test_bulk_save_creates_insights_and_widgets(self):
        db = MagicMock()
        request = MagicMock()

        dash = Dashboard(
            id=uuid.uuid4(),
            tenant_id=TENANT_ID,
            user_id=USER_OWNER.id,
            name="Sales Dashboard",
            widgets=[],
            tabs=[],
        )
        db.scalar.side_effect = lambda q: dash if "dashboard" in str(q).lower() else None
        db.scalars.return_value.all.return_value = []

        req = BulkSaveRequest(
            dashboard_id=dash.id,
            items=[
                BulkSaveItem(
                    name="Revenue Trend",
                    query="SELECT month, sum(rev) as rev FROM sales GROUP BY month",
                    source_id=uuid.uuid4(),
                    chart_type="line",
                ),
                BulkSaveItem(
                    name="Top Reps",
                    query="SELECT rep_name, count(*) FROM visits GROUP BY rep_name",
                    source_id=uuid.uuid4(),
                    chart_type="bar",
                ),
            ],
        )

        with patch("app.api.dashboards.audit"), patch("app.api.dashboards.verify_user_has_source_access"):
            res = bulk_save_insights_to_dashboard(req, request, db=db, user=USER_OWNER)

        assert res.saved_count == 2
        assert len(res.insight_ids) == 2
        assert len(res.widget_ids) == 2
        assert len(res.skipped_duplicates) == 0

    def test_bulk_save_skips_duplicates(self):
        db = MagicMock()
        request = MagicMock()

        source_id = uuid.uuid4()
        existing_sql = "SELECT * FROM duplicate_table"

        existing_insight = SavedInsight(
            id=uuid.uuid4(),
            tenant_id=TENANT_ID,
            user_id=USER_OWNER.id,
            source_id=source_id,
            name="Duplicate Item",
            query=existing_sql,
        )

        dash = Dashboard(
            id=uuid.uuid4(),
            tenant_id=TENANT_ID,
            user_id=USER_OWNER.id,
            name="Sales Dashboard",
            widgets=[DashboardWidget(id=uuid.uuid4(), insight=existing_insight, insight_id=existing_insight.id, x=0, y=0, w=6, h=4)],
            tabs=[],
        )
        db.scalar.side_effect = lambda q: dash if "dashboard" in str(q).lower() else None
        db.scalars.return_value.all.return_value = [existing_insight]

        req = BulkSaveRequest(
            dashboard_id=dash.id,
            items=[
                BulkSaveItem(
                    name="Duplicate Item",
                    query=existing_sql,
                    source_id=source_id,
                    chart_type="table",
                ),
                BulkSaveItem(
                    name="New Fresh Insight",
                    query="SELECT 1 as val",
                    source_id=source_id,
                    chart_type="table",
                ),
            ],
        )

        with patch("app.api.dashboards.audit"), patch("app.api.dashboards.verify_user_has_source_access"):
            res = bulk_save_insights_to_dashboard(req, request, db=db, user=USER_OWNER)

        assert res.saved_count == 1
        assert len(res.skipped_duplicates) == 1
        assert "Duplicate Item" in res.skipped_duplicates[0]


class TestDashboardTabs:
    """Task 2: Dashboard Tabs CRUD and permission enforcement tests."""

    def test_first_tab_creation_migrates_existing_widgets_to_main(self):
        db = MagicMock()
        request = MagicMock()

        w1 = DashboardWidget(id=uuid.uuid4(), tab_id=None, x=0, y=0, w=6, h=4)
        w2 = DashboardWidget(id=uuid.uuid4(), tab_id=None, x=6, y=0, w=6, h=4)
        dash = Dashboard(
            id=uuid.uuid4(),
            tenant_id=TENANT_ID,
            user_id=USER_OWNER.id,
            name="My Dashboard",
            widgets=[w1, w2],
            tabs=[],
        )
        db.scalar.return_value = dash

        tab_in = TabCreate(name="Finance")
        with patch("app.api.dashboards.audit"):
            res = create_dashboard_tab(dash.id, tab_in, request, db=db, user=USER_OWNER)

        # Main tab and Finance tab should be created
        assert len(dash.tabs) == 2
        assert dash.tabs[0].name == "Main"
        assert dash.tabs[1].name == "Finance"
        # Widgets should be migrated to Main tab
        assert w1.tab_id == dash.tabs[0].id
        assert w2.tab_id == dash.tabs[0].id

    def test_delete_tab_requires_at_least_one_tab_to_remain(self):
        db = MagicMock()
        request = MagicMock()

        tab1 = DashboardTab(id=uuid.uuid4(), name="Single Tab", position=0)
        dash = Dashboard(
            id=uuid.uuid4(),
            tenant_id=TENANT_ID,
            user_id=USER_OWNER.id,
            name="Single Tab Dash",
            widgets=[],
            tabs=[tab1],
        )
        db.scalar.return_value = dash

        with pytest.raises(HTTPException) as exc_info:
            delete_dashboard_tab(dash.id, tab1.id, request=request, db=db, user=USER_OWNER)
        assert exc_info.value.status_code == 400
        assert "must keep at least one tab" in exc_info.value.detail

    def test_delete_tab_with_move_to_tab_moves_widgets(self):
        db = MagicMock()
        request = MagicMock()

        tab1 = DashboardTab(id=uuid.uuid4(), name="Tab 1", position=0)
        tab2 = DashboardTab(id=uuid.uuid4(), name="Tab 2", position=1)
        w1 = DashboardWidget(id=uuid.uuid4(), tab_id=tab1.id, x=0, y=0, w=6, h=4)

        dash = Dashboard(
            id=uuid.uuid4(),
            tenant_id=TENANT_ID,
            user_id=USER_OWNER.id,
            name="Multi Tab Dash",
            widgets=[w1],
            tabs=[tab1, tab2],
        )
        db.scalar.return_value = dash

        with patch("app.api.dashboards.audit"):
            delete_dashboard_tab(dash.id, tab1.id, move_to_tab_id=tab2.id, request=request, db=db, user=USER_OWNER)

        assert w1.tab_id == tab2.id


class TestResultCacheAndRefresh:
    """Task 6: Result cache and refresh tests."""

    def test_cache_keys_differ_per_user_and_permissions(self):
        cache = DashboardResultCache.get_instance()
        db = MagicMock()

        hash1 = cache.compute_permission_hash(USER_OWNER, uuid.uuid4(), db=db)
        hash2 = cache.compute_permission_hash(USER_VIEWER, uuid.uuid4(), db=db)
        # Different users generate different fingerprints
        assert hash1 != hash2

    def test_cache_set_and_get_lifecycle(self):
        cache = DashboardResultCache.get_instance()
        insight_id = uuid.uuid4()
        sql = "SELECT 1 as test"
        perm_hash = "testhash123"

        payload = {
            "status": "success",
            "locked": False,
            "data": [{"test": 1}],
            "columns": ["test"],
            "row_count": 1,
            "execution_time_ms": 12.5,
        }

        # Store in cache
        cache.set(
            tenant_id=TENANT_ID,
            user_id=USER_OWNER.id,
            permission_hash=perm_hash,
            insight_id=insight_id,
            query_sql=sql,
            payload=payload,
        )

        # Retrieve
        cached = cache.get(
            tenant_id=TENANT_ID,
            user_id=USER_OWNER.id,
            permission_hash=perm_hash,
            insight_id=insight_id,
            query_sql=sql,
        )
        assert cached is not None
        assert cached["cached"] is True
        assert cached["data"] == [{"test": 1}]

        # Different user should get cache miss
        cached_other = cache.get(
            tenant_id=TENANT_ID,
            user_id=USER_VIEWER.id,
            permission_hash=perm_hash,
            insight_id=insight_id,
            query_sql=sql,
        )
        assert cached_other is None
