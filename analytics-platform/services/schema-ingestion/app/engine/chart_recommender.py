"""Chart Recommender.

Deterministically selects appropriate visualization types based on query plan attributes,
dimension counts, time intelligence, measure counts, and result row/column metrics.
"""
from app.schemas_engine import LogicalQueryPlan

PIE_MAX_SLICES = 6
CAROUSEL_MAX_CARDS = 12


class ChartRecommender:
    @staticmethod
    def recommend(plan: LogicalQueryPlan, row_count: int = 0, column_count: int = 0) -> str:
        # 1. Use the LLM's recommended chart if explicitly specified
        if plan.chart_recommendation:
            return plan.chart_recommendation

        # 2. KPI Card for zero rows or single scalar result
        if row_count == 0 or (row_count == 1 and column_count <= 1 and len(plan.dimension_ids) == 0):
            return "kpi_card"

        # 3. Line Chart for time series data
        if plan.time_granularity or plan.time_intelligence:
            return "line_chart"

        dim_count = len(plan.dimension_ids)

        # 4. Pie Chart for single dimension + 1 measure with 2 to 6 rows
        if dim_count == 1 and 2 <= row_count <= PIE_MAX_SLICES:
            return "pie_chart"

        # 5. Carousel Cards for multi-dimension or entity cards capped at ~12 rows
        if (dim_count >= 2 or column_count > 3) and 2 <= row_count <= CAROUSEL_MAX_CARDS:
            return "carousel_cards"

        # 6. Bar Chart for single dimension
        if dim_count == 1:
            return "bar_chart"

        # 7. Fallback to data table
        return "table"
