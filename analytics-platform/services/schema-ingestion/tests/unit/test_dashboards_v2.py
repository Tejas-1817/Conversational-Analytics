"""
Comprehensive unit tests for Dashboards v2:
- Authorization matrix (owner, other user in tenant, other tenant, VIEWER observer)
- Private vs. published visibility filtering
- In-place widget layout updates (widget ID preservation)
- Deleting insights used on dashboards (409 conflict prevention)
- Saving insight strips raw snapshot rows and does NOT promote to ApprovedSQLExample
- Dynamic Run endpoint with table permissions, source access, and PII masking
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
from fastapi import HTTPException

from app.api.dashboards import (
    create_dashboard,
    list_dashboards,
    get_dashboard,
    update_dashboard_metadata,
    delete_dashboard,
    update_dashboard_layout,
    create_insight,
    delete_insight,
    run_insight,
    DashboardCreate,
    DashboardUpdate,
    DashboardLayoutUpdate,
    InsightCreate,
    WidgetLayoutItem,
    extract_tables_from_query,
    mask_result_rows,
)
from app.models import (
    Dashboard,
    DashboardWidget,
    SavedInsight,
    User,
    DataSource,
    TableMeta,
    ApprovedSQLExample,
)


# Test tenant and user fixtures
TENANT_A = uuid.uuid4()
TENANT_B = uuid.uuid4()

USER_OWNER = User(
    id=uuid.uuid4(),
    tenant_id=TENANT_A,
    email="owner@example.com",
    role="USER",
    is_active=True,
)

USER_OTHER = User(
    id=uuid.uuid4(),
    tenant_id=TENANT_A,
    email="other@example.com",
    role="USER",
    is_active=True,
)

USER_OBSERVER = User(
    id=uuid.uuid4(),
    tenant_id=TENANT_A,
    email="observer@example.com",
    role="VIEWER",
    is_active=True,
)

USER_ADMIN = User(
    id=uuid.uuid4(),
    tenant_id=TENANT_A,
    email="admin@example.com",
    role="ADMIN",
    is_active=True,
)

USER_TENANT_B = User(
    id=uuid.uuid4(),
    tenant_id=TENANT_B,
    email="tenant_b@example.com",
    role="USER",
    is_active=True,
)


class TestTableExtractionAndPIIMasking:
    """Tests for SQL table extraction and PII masking helpers."""

    def test_extract_tables_simple_and_join(self):
        sql = "SELECT c.name, o.total FROM customers c JOIN orders o ON c.id = o.customer_id"
        tables = extract_tables_from_query(sql, dialect="postgres")
        assert "customers" in tables
        assert "orders" in tables

    def test_extract_tables_ignores_ctes(self):
        sql = "WITH regional_sales AS (SELECT * FROM sales) SELECT * FROM regional_sales"
        tables = extract_tables_from_query(sql, dialect="postgres")
        assert "sales" in tables
        assert "regional_sales" not in tables

    def test_mask_result_rows_masks_sensitive_columns_and_values(self):
        rows = [
            {"email": "secret@company.com", "name": "Alice", "revenue": 100},
            {"email": "bob@org.org", "name": "Bob", "revenue": 200},
        ]
        columns = ["email", "name", "revenue"]
        masked = mask_result_rows(rows, columns)
        assert len(masked) == 2
        assert masked[0]["email"] == "<masked: sensitive column>"
        assert masked[0]["name"] == "Alice"
        assert masked[0]["revenue"] == 100


class TestDashboardsAPI:
    """Unit tests for Dashboard & Insight API endpoints."""

    def setup_method(self):
        self.mock_db = MagicMock()
        self.mock_request = MagicMock()

    def test_observer_cannot_create_dashboard(self):
        """VIEWER (Observer) role must be forbidden from creating dashboards."""
        with pytest.raises(HTTPException) as exc_info:
            create_dashboard(
                dash=DashboardCreate(name="Observer Dashboard"),
                request=self.mock_request,
                db=self.mock_db,
                user=USER_OBSERVER,
            )
        assert exc_info.value.status_code == 403
        assert "Observers have read-only access" in exc_info.value.detail

    def test_observer_cannot_create_insight(self):
        """VIEWER (Observer) role must be forbidden from creating insights."""
        with pytest.raises(HTTPException) as exc_info:
            create_insight(
                insight=InsightCreate(name="Obs Insight", query="SELECT 1"),
                request=self.mock_request,
                db=self.mock_db,
                user=USER_OBSERVER,
            )
        assert exc_info.value.status_code == 403
        assert "Observers have read-only access" in exc_info.value.detail

    def test_create_dashboard_duplicate_name_returns_409(self):
        """Same user cannot create two dashboards with identical names."""
        existing_dash = Dashboard(
            id=uuid.uuid4(),
            tenant_id=USER_OWNER.tenant_id,
            user_id=USER_OWNER.id,
            name="Revenue Overview",
            visibility="private",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.mock_db.scalar.return_value = existing_dash

        with pytest.raises(HTTPException) as exc_info:
            create_dashboard(
                dash=DashboardCreate(name="Revenue Overview"),
                request=self.mock_request,
                db=self.mock_db,
                user=USER_OWNER,
            )
        assert exc_info.value.status_code == 409
        assert "already exists for your account" in exc_info.value.detail

    def test_get_private_dashboard_by_other_user_returns_404(self):
        """A private dashboard is invisible to other users in the same tenant (404)."""
        dash_id = uuid.uuid4()
        private_dash = Dashboard(
            id=dash_id,
            tenant_id=TENANT_A,
            user_id=USER_OWNER.id,
            name="Owner Private",
            visibility="private",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            widgets=[],
        )
        self.mock_db.scalar.return_value = private_dash

        with pytest.raises(HTTPException) as exc_info:
            get_dashboard(
                dash_id=dash_id,
                db=self.mock_db,
                user=USER_OTHER,
            )
        assert exc_info.value.status_code == 404

    def test_get_published_dashboard_by_other_user_succeeds(self):
        """A published dashboard can be read by other users in the tenant."""
        dash_id = uuid.uuid4()
        published_dash = Dashboard(
            id=dash_id,
            tenant_id=TENANT_A,
            user_id=USER_OWNER.id,
            name="Published Overview",
            visibility="published",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            widgets=[],
        )
        self.mock_db.scalar.return_value = published_dash

        res = get_dashboard(
            dash_id=dash_id,
            db=self.mock_db,
            user=USER_OTHER,
        )
        assert res.name == "Published Overview"

    def test_other_user_cannot_update_or_delete_dashboard(self):
        """Non-owner non-admin cannot edit or delete another user's dashboard (403)."""
        dash_id = uuid.uuid4()
        dash = Dashboard(
            id=dash_id,
            tenant_id=TENANT_A,
            user_id=USER_OWNER.id,
            name="Owner Dash",
            visibility="published",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            widgets=[],
        )
        self.mock_db.scalar.return_value = dash

        # Attempt PATCH
        with pytest.raises(HTTPException) as exc_patch:
            update_dashboard_metadata(
                dash_id=dash_id,
                dash_update=DashboardUpdate(name="Hacked Name"),
                request=self.mock_request,
                db=self.mock_db,
                user=USER_OTHER,
            )
        assert exc_patch.value.status_code == 403
        assert "Only the dashboard owner" in exc_patch.value.detail

        # Attempt DELETE
        with pytest.raises(HTTPException) as exc_del:
            delete_dashboard(
                dash_id=dash_id,
                request=self.mock_request,
                db=self.mock_db,
                user=USER_OTHER,
            )
        assert exc_del.value.status_code == 403
        assert "Only the dashboard owner" in exc_del.value.detail

    def test_save_insight_strips_raw_rows_and_does_not_touch_approved_sql(self):
        """
        Saving an insight must NOT add an ApprovedSQLExample and must sanitize raw data rows.
        """
        self.mock_db.scalar.return_value = None  # No duplicate

        payload = InsightCreate(
            name="Conversion by Channel",
            query="SELECT channel, count(*) FROM conversions GROUP BY channel",
            chart_type="bar",
            chart_config={
                "chartType": "bar",
                "columns": ["channel", "count"],
                "data": [{"channel": "email", "count": 1000}, {"channel": "ad", "count": 500}],
            },
        )

        with patch("app.api.dashboards.audit") as mock_audit:
            res = create_insight(
                insight=payload,
                request=self.mock_request,
                db=self.mock_db,
                user=USER_OWNER,
            )
            assert res is not None

            # Check added SavedInsight instance
            added_objects = [call[0][0] for call in self.mock_db.add.call_args_list]
            saved_insight = next(obj for obj in added_objects if isinstance(obj, SavedInsight))

            # Raw snapshot rows stripped from chart_config
            assert saved_insight.chart_config.get("data") == []
            assert saved_insight.chart_config.get("columns") == ["channel", "count"]

            # ApprovedSQLExample was NOT added
            approved_examples = [obj for obj in added_objects if isinstance(obj, ApprovedSQLExample)]
            assert len(approved_examples) == 0

            # Audit log was recorded
            mock_audit.assert_called_once()
            assert mock_audit.call_args.kwargs["action"] == "create_insight"

    def test_delete_insight_blocked_when_used_on_dashboards(self):
        """Deleting an insight that is placed on a dashboard must return 409 Conflict."""
        insight_id = uuid.uuid4()
        insight = SavedInsight(
            id=insight_id,
            tenant_id=TENANT_A,
            user_id=USER_OWNER.id,
            name="Active Metric",
            query="SELECT 1",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.mock_db.scalar.return_value = insight

        # Mock that this insight is used on "Sales Exec" dashboard
        self.mock_db.scalars.return_value.all.return_value = ["Sales Exec"]

        with pytest.raises(HTTPException) as exc_info:
            delete_insight(
                insight_id=insight_id,
                request=self.mock_request,
                db=self.mock_db,
                user=USER_OWNER,
            )
        assert exc_info.value.status_code == 409
        assert "Cannot delete insight 'Active Metric' because it is in use" in exc_info.value.detail
        assert "Sales Exec" in exc_info.value.detail

    def test_update_dashboard_layout_in_place_preserves_widget_id(self):
        """PUT /dashboards/{id}/layout must update widgets in place and keep widget IDs."""
        dash_id = uuid.uuid4()
        widget_id = uuid.uuid4()

        widget = DashboardWidget(
            id=widget_id,
            dashboard_id=dash_id,
            insight_id=uuid.uuid4(),
            x=0,
            y=0,
            w=6,
            h=4,
            layouts={"lg": {"x": 0, "y": 0, "w": 6, "h": 4}},
        )

        dash = Dashboard(
            id=dash_id,
            tenant_id=TENANT_A,
            user_id=USER_OWNER.id,
            name="My Dashboard",
            visibility="private",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            widgets=[widget],
        )

        # First scalar call is get_dashboard_or_404, scalars call is existing_widgets, final scalar is return
        self.mock_db.scalar.return_value = dash
        self.mock_db.scalars.return_value.all.return_value = [widget]

        res = update_dashboard_layout(
            dash_id=dash_id,
            layout_update=DashboardLayoutUpdate(
                widgets=[
                    WidgetLayoutItem(
                        widget_id=widget_id,
                        x=6,
                        y=4,
                        w=6,
                        h=5,
                        layouts={"lg": {"x": 6, "y": 4, "w": 6, "h": 5}},
                    )
                ]
            ),
            db=self.mock_db,
            user=USER_OWNER,
        )
        assert res is not None
        # Widget position updated in place
        assert widget.x == 6
        assert widget.y == 4
        assert widget.w == 6
        assert widget.h == 5
        assert widget.id == widget_id

    @patch("app.api.dashboards.verify_user_has_source_access")
    @patch("app.api.dashboards.get_user_permitted_table_ids")
    @patch("app.api.dashboards.SQLExecutor.execute_query")
    def test_run_insight_success_and_locked_on_permission_denial(
        self, mock_exec, mock_table_perms, mock_source_access
    ):
        """
        Verify the live run endpoint:
        - Lacking table permission returns status='locked' with locked=True.
        - With permission returns status='success' and masked rows.
        """
        source_id = uuid.uuid4()
        table_id = uuid.uuid4()
        insight_id = uuid.uuid4()

        insight = SavedInsight(
            id=insight_id,
            tenant_id=TENANT_A,
            user_id=USER_OWNER.id,
            name="Confidential Revenue",
            query="SELECT email, amount FROM customer_contracts",
            source_id=source_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        source = DataSource(
            id=source_id,
            tenant_id=TENANT_A,
            name="Customer DB",
            type="postgres",
        )

        table_meta = TableMeta(
            id=table_id,
            source_id=source_id,
            table_name="customer_contracts",
        )

        # Case 1: Lacking table permission -> status="locked"
        self.mock_db.scalar.side_effect = [insight, uuid.uuid4(), source]
        self.mock_db.scalars.return_value.all.return_value = [table_meta]
        mock_table_perms.return_value = set()  # User has no table access

        res_locked = run_insight(
            insight_id=insight_id,
            db=self.mock_db,
            user=USER_OTHER,
        )
        assert res_locked.status == "locked"
        assert res_locked.locked is True
        assert "customer_contracts" in res_locked.detail

        # Case 2: Permitted table access -> status="success" and PII masked
        self.mock_db.scalar.side_effect = [insight, uuid.uuid4(), source]
        self.mock_db.scalars.return_value.all.return_value = [table_meta]
        mock_table_perms.return_value = {table_id}  # Granted
        mock_exec.return_value = (
            [{"email": "john@corp.com", "amount": 50000}],
            1,
            12.5,
            ["email", "amount"],
            None,
            False,
        )

        res_ok = run_insight(
            insight_id=insight_id,
            db=self.mock_db,
            user=USER_OTHER,
        )
        assert res_ok.status == "success"
        assert res_ok.locked is False
        assert res_ok.data[0]["email"] == "<masked: sensitive column>"
        assert res_ok.data[0]["amount"] == 50000
