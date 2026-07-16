from app.schemas_engine import LogicalQueryPlan


class ChartRecommender:
    @staticmethod
    def recommend(plan: LogicalQueryPlan) -> str:
        # 1. Use the LLM's recommended chart if available
        if plan.chart_recommendation:
            return plan.chart_recommendation
            
        # 2. Fallback to deterministic recommendation
        if plan.time_granularity or plan.time_intelligence:
            return "line_chart"

        if len(plan.dimension_ids) == 0:
            return "kpi_card"

        if len(plan.dimension_ids) == 1:
            return "bar_chart"

        return "table"
