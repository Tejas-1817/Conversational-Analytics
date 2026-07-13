from app.schemas_engine import StructuredQueryPlan

class ChartRecommender:
    @staticmethod
    def recommend(plan: StructuredQueryPlan) -> str:
        # Deterministic chart recommendation based on the shape of the query
        if plan.time_granularity:
            return "line_chart"
            
        if len(plan.dimension_ids) == 0:
            return "kpi_card"
            
        if len(plan.dimension_ids) == 1:
            return "bar_chart"
            
        return "table"
