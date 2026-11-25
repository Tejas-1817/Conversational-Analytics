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


def test_chart_recommender_pattern_a_titles():
    # 1. Multi-metric categorical comparison (e.g. Risk & News by Customer)
    rows = [
        {"customer_name": "Acme Corp", "negative_news_count": 3, "revenue_at_risk": 500000},
        {"customer_name": "Globex", "negative_news_count": 2, "revenue_at_risk": 250000},
    ]
    cols = ["customer_name", "negative_news_count", "revenue_at_risk"]
    rec = ChartRecommender.recommend_visualization(rows, cols, question="Show accounts at risk")
    assert rec["title"] == "Negative News Count & Revenue At Risk by Customer"

    # 2. Direct static method infer_title with time series
    time_rows = [
        {"created_month": "2026-01-01", "mrr": 120000},
        {"created_month": "2026-02-01", "mrr": 135000},
    ]
    t_title = ChartRecommender.infer_title(time_rows, ["created_month", "mrr"])
    assert "MRR over Created Month" in t_title or "MRR by Created Month" in t_title

    # 3. Healthcare / IoT arbitrary schema
    iot_rows = [
        {"sensor_location": "Building A", "avg_temperature": 22.4, "alert_count": 5},
    ]
    iot_title = ChartRecommender.infer_title(iot_rows, ["sensor_location", "avg_temperature", "alert_count"])
    assert "Sensor Location" in iot_title and "Avg Temperature" in iot_title

