"""Unit tests for ChartRecommender (Gap 3)."""
import uuid
from unittest.mock import MagicMock

from app.engine.chart_recommender import CAROUSEL_MAX_CARDS, PIE_MAX_SLICES, ChartRecommender
from app.schemas_engine import LogicalQueryPlan


def test_chart_recommender_explicit_llm_choice():
    plan = MagicMock(spec=LogicalQueryPlan)
    plan.chart_recommendation = "bar_chart"
    assert ChartRecommender.recommend(plan) == "bar_chart"


def test_chart_recommender_kpi_card_for_scalar():
    plan = MagicMock(spec=LogicalQueryPlan)
    plan.chart_recommendation = None
    plan.dimension_ids = []
    assert ChartRecommender.recommend(plan, row_count=1, column_count=1) == "kpi_card"


def test_chart_recommender_line_chart_for_time():
    plan = MagicMock(spec=LogicalQueryPlan)
    plan.chart_recommendation = None
    plan.time_granularity = "MONTH"
    plan.time_intelligence = None
    plan.dimension_ids = [uuid.uuid4()]
    assert ChartRecommender.recommend(plan, row_count=10, column_count=2) == "line_chart"


def test_chart_recommender_pie_chart_for_small_single_dimension():
    plan = MagicMock(spec=LogicalQueryPlan)
    plan.chart_recommendation = None
    plan.time_granularity = None
    plan.time_intelligence = None
    plan.dimension_ids = [uuid.uuid4()]
    assert ChartRecommender.recommend(plan, row_count=5, column_count=2) == "pie_chart"


def test_chart_recommender_carousel_cards_for_multi_dimension():
    plan = MagicMock(spec=LogicalQueryPlan)
    plan.chart_recommendation = None
    plan.time_granularity = None
    plan.time_intelligence = None
    plan.dimension_ids = [uuid.uuid4(), uuid.uuid4()]
    assert ChartRecommender.recommend(plan, row_count=8, column_count=4) == "carousel_cards"


def test_chart_recommender_table_fallback():
    plan = MagicMock(spec=LogicalQueryPlan)
    plan.chart_recommendation = None
    plan.time_granularity = None
    plan.time_intelligence = None
    plan.dimension_ids = [uuid.uuid4(), uuid.uuid4()]
    assert ChartRecommender.recommend(plan, row_count=50, column_count=5) == "table"
