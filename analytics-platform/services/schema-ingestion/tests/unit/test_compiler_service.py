"""Unit tests for CompilerService.

Rules from testing.md:
- No DB, no network, no real secrets.
- Write the failing test first (proven here by the bug description), then fix.
- Test names describe behaviour, not implementation.

Mock strategy: instead of string-inspecting SQLAlchemy compiled statements (fragile),
we patch CompilerService._resolve_column directly for tests that need full column
resolution, and use a thin scalar-dispatch mock for simpler cases.
"""
import uuid
from unittest.mock import MagicMock

import pytest

from app.engine.compiler_service import (
    ColumnResolutionError,
    CompilerService,
    SQLSafetyError,
)
from app.models import ColumnMeta, SemanticDimension, SemanticMetric, TableMeta
from app.schemas_engine import LogicalQueryPlan, QueryPlanFilter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_table(name: str = "fct_sales") -> TableMeta:
    tbl = MagicMock(spec=TableMeta)
    tbl.id = uuid.uuid4()
    tbl.table_name = name
    return tbl


def _make_col(table_id: uuid.UUID, name: str = "amount") -> ColumnMeta:
    col = MagicMock(spec=ColumnMeta)
    col.id = uuid.uuid4()
    col.table_id = table_id
    col.column_name = name
    return col


def _make_metric(
    table_id: uuid.UUID,
    column_id: uuid.UUID,
    tenant_id: uuid.UUID | None = None,
    agg: str = "SUM",
) -> SemanticMetric:
    m = MagicMock(spec=SemanticMetric)
    m.id = uuid.uuid4()
    m.tenant_id = tenant_id or uuid.uuid4()
    m.name = "Revenue"
    m.source_table_id = table_id
    m.source_column_id = column_id
    m.aggregation_type = agg
    return m


def _make_dimension(
    source_column_id: uuid.UUID | None,
    business_name: str = "Sale Region",
) -> SemanticDimension:
    dim = MagicMock(spec=SemanticDimension)
    dim.id = uuid.uuid4()
    dim.business_name = business_name
    dim.source_column_id = source_column_id
    return dim


def _scalar_returns(*return_values):
    """Return a mock db.scalar that yields successive return values in order."""
    values = list(return_values)
    call_count = [0]

    def _side(stmt):
        idx = call_count[0]
        call_count[0] += 1
        if idx < len(values):
            return values[idx]
        return None

    db = MagicMock()
    db.scalar.side_effect = _side
    return db


# ---------------------------------------------------------------------------
# Tests: dimension resolves to its actual source column, not a string transform
# ---------------------------------------------------------------------------

class TestDimensionColumnResolution:
    def test_dimension_uses_real_column_name_not_business_name_transform(self):
        """The generated SQL GROUP BY must reference the real column name from ColumnMeta,
        not a string-transformed version of the dimension's business_name.

        Bug: old code did `dim.business_name.lower().replace(' ', '_')` producing
        'sale_region' instead of looking up ColumnMeta and getting the actual column
        (e.g. 'geo_region').
        """
        tbl = _make_table("fct_orders")
        metric_col = _make_col(tbl.id, "revenue")
        # The real column name in the DB is 'geo_region', NOT 'sale_region'
        dim_col = _make_col(tbl.id, "geo_region")
        tenant_id = uuid.uuid4()
        metric = _make_metric(tbl.id, metric_col.id, tenant_id=tenant_id)
        dim = _make_dimension(dim_col.id, business_name="Sale Region")

        plan = LogicalQueryPlan(
            intent="aggregate",
            metric_ids=[metric.id],
            dimension_ids=[dim.id],
        )

        # db.scalar is called in this order by compile_plan:
        # 1. load metric (SemanticMetric)
        # 2. _resolve_column for metric → ColumnMeta (metric_col)
        # 3. _resolve_column for metric → TableMeta (tbl)
        # 4. load dimension (SemanticDimension)
        # 5. _resolve_column for dim → ColumnMeta (dim_col)
        # 6. _resolve_column for dim → TableMeta (tbl)
        db = _scalar_returns(metric, metric_col, tbl, dim, dim_col, tbl)

        compiled = CompilerService.compile_plan(db, tenant_id, plan)

        assert "geo_region" in compiled.sql, (
            f"Expected real column name 'geo_region' in SQL, got:\n{compiled.sql}"
        )
        assert "sale_region" not in compiled.sql, (
            f"SQL must NOT contain the business_name transform 'sale_region':\n{compiled.sql}"
        )
        assert "fct_orders.geo_region" in compiled.sql

    def test_dimension_without_source_column_id_raises_resolution_error(self):
        """A dimension that has no source_column_id set must raise ColumnResolutionError,
        not fall back to guessing a column name."""
        tbl = _make_table()
        metric_col = _make_col(tbl.id, "revenue")
        tenant_id = uuid.uuid4()
        metric = _make_metric(tbl.id, metric_col.id, tenant_id=tenant_id)
        dim = _make_dimension(source_column_id=None, business_name="Mystery Dim")

        plan = LogicalQueryPlan(
            intent="aggregate",
            metric_ids=[metric.id],
            dimension_ids=[dim.id],
        )

        db = _scalar_returns(metric, metric_col, tbl, dim)

        with pytest.raises(ColumnResolutionError, match="no source_column_id"):
            CompilerService.compile_plan(db, tenant_id, plan)

    def test_multi_word_metric_alias_is_quoted(self):
        """A metric name with multiple words must be quoted in the AS alias.
        
        Bug: unquoted aliases like `as Total Revenue` caused SQL syntax errors.
        """
        tbl = _make_table("fct_orders")
        metric_col = _make_col(tbl.id, "revenue")
        tenant_id = uuid.uuid4()
        # Create metric with a multi-word name
        metric = _make_metric(tbl.id, metric_col.id, tenant_id=tenant_id)
        metric.name = "Total Revenue"
        
        plan = LogicalQueryPlan(
            intent="aggregate",
            metric_ids=[metric.id],
            dimension_ids=[],
        )
        
        # scalar calls: metric, metric_col, tbl
        db = _scalar_returns(metric, metric_col, tbl)
        
        compiled = CompilerService.compile_plan(db, tenant_id, plan)
        
        assert '"Total Revenue"' in compiled.sql, f"Expected quoted alias, got: {compiled.sql}"
        assert 'as Total Revenue' not in compiled.sql, "Alias must not be unquoted"



# ---------------------------------------------------------------------------
# Tests: filter uses real column name, not hardcoded 'filter_col'
# ---------------------------------------------------------------------------

class TestFilterColumnResolution:
    def test_filter_on_arbitrary_field_produces_sql_with_correct_real_column(self):
        """A filter's column_id must be resolved via ColumnMeta to get the actual column name.

        Bug: old code hardcoded the literal string 'filter_col' for every filter
        regardless of what the user filtered on, producing invalid SQL.
        """
        tbl = _make_table("fct_sales")
        metric_col = _make_col(tbl.id, "amount")
        # The filter is on a column called 'order_status', not 'filter_col'
        filter_col = _make_col(tbl.id, "order_status")
        tenant_id = uuid.uuid4()
        metric = _make_metric(tbl.id, metric_col.id, tenant_id=tenant_id)

        plan = LogicalQueryPlan(
            intent="aggregate",
            metric_ids=[metric.id],
            filters=[QueryPlanFilter(column_id=filter_col.id, operator="=", value="completed")],
        )

        # scalar calls: metric, metric_col, tbl, filter_col, tbl
        db = _scalar_returns(metric, metric_col, tbl, filter_col, tbl)

        compiled = CompilerService.compile_plan(db, tenant_id, plan)

        assert "order_status" in compiled.sql, (
            f"Expected 'order_status' in WHERE clause, got:\n{compiled.sql}"
        )
        assert "filter_col" not in compiled.sql, (
            f"SQL must NOT contain the hardcoded 'filter_col' literal:\n{compiled.sql}"
        )
        assert ":filter_0" in compiled.sql
        assert compiled.params["filter_0"] == "completed"

    def test_filter_column_id_not_in_catalog_raises_resolution_error(self):
        """A filter whose column_id has no ColumnMeta row must raise ColumnResolutionError."""
        tbl = _make_table()
        metric_col = _make_col(tbl.id, "amount")
        tenant_id = uuid.uuid4()
        metric = _make_metric(tbl.id, metric_col.id, tenant_id=tenant_id)

        plan = LogicalQueryPlan(
            intent="aggregate",
            metric_ids=[metric.id],
            filters=[QueryPlanFilter(column_id=uuid.uuid4(), operator="=", value="x")],
        )

        # scalar calls: metric, metric_col, tbl, None (filter_col not found)
        db = _scalar_returns(metric, metric_col, tbl, None)

        with pytest.raises(ColumnResolutionError, match="ColumnMeta not found"):
            CompilerService.compile_plan(db, tenant_id, plan)


# ---------------------------------------------------------------------------
# Tests: SQL safety guardrails still pass (regression)
# ---------------------------------------------------------------------------

class TestSQLSafetyGuardrails:
    @pytest.mark.parametrize("bad_sql", [
        "SELECT amount FROM orders; DROP TABLE orders",
        "UPDATE orders SET amount = 0 WHERE 1=1",
        "DELETE FROM orders",
        "INSERT INTO orders VALUES (1)",
        "SELECT * FROM orders",
    ])
    def test_forbidden_sql_is_rejected(self, bad_sql: str):
        with pytest.raises(SQLSafetyError):
            CompilerService.validate_safety(bad_sql)

    def test_valid_aggregate_sql_passes_safety(self):
        sql = (
            "SELECT SUM(fct_sales.amount) as Revenue FROM fct_sales "
            "WHERE fct_sales.tenant_id = :tenant_id LIMIT 100"
        )
        CompilerService.validate_safety(sql)  # must not raise
