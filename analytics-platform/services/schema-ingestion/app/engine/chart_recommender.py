"""Chart Recommender — Deterministic Enterprise Visualization Recommendation Engine."""
import re
import structlog
from typing import Any, Dict, List, Optional
from app.engine.result_inspector import ResultInspector

log = structlog.get_logger(__name__)


def _infer_title(question: str, columns: List[str], visualization: str) -> str:
    """Infers clean, non-hardcoded title from user question or column names."""
    if question and question.strip():
        clean_q = question.strip()
        clean_q = re.sub(r"\?$", "", clean_q)
        words = clean_q.split()
        if len(words) <= 8:
            return clean_q.title()
        return clean_q

    if columns:
        col_name = columns[0].replace("_", " ").title()
        if len(columns) > 1:
            val_name = columns[1].replace("_", " ").title()
            return f"{col_name} vs {val_name}"
        return col_name

    return "Query Results"


class ChartRecommender:
    """Deterministic Visualization Recommendation Engine based on SQL result metadata."""

    @staticmethod
    def recommend_visualization(
        rows: List[Dict[str, Any]],
        columns: List[str],
        question: str = "",
        sql: str = ""
    ) -> Dict[str, Any]:
        """Applies 9 deterministic rules to determine exact visualization payload."""
        profile = ResultInspector.profile_dataset(rows, columns, sql=sql)
        rc = profile["row_count"]
        cols = profile["columns"]
        cc = profile["column_count"]
        title = _infer_title(question, cols, "")

        num_cols = profile["numeric_columns"]
        cat_cols = profile["categorical_columns"]
        time_cols = profile["time_columns"]
        pct_cols = profile["percentage_columns"]
        is_top_n = profile["is_top_n"]

        visualization = "table"
        chart_type = "table"
        rendered_component = "DataGrid"
        reason = "Tabular dataset default."

                # 1. Zero rows check
        if rc == 0:
            visualization = "table"
            chart_type = "table"
            rendered_component = "NoData"
            reason = "No matching records found."

        # 1b. Priority 0: Explicit user chart request in the prompt
        elif any(k in (question or "").lower() for k in ["bar chart", "bar graph", "horizontal bar", "column chart"]):
            visualization = "bar_chart"
            chart_type = "bar_chart"
            rendered_component = "BarChart"
            reason = "User explicitly requested a bar chart."

        elif any(k in (question or "").lower() for k in ["line chart", "line graph", "trend chart", "timeseries", "over time"]):
            visualization = "line_chart"
            chart_type = "line_chart"
            rendered_component = "LineChart"
            reason = "User explicitly requested a line chart or trend."

        elif any(k in (question or "").lower() for k in ["pie chart", "donut chart", "pie", "share of", "percentage distribution"]):
            visualization = "pie_chart"
            chart_type = "pie_chart"
            rendered_component = "PieChart"
            reason = "User explicitly requested a pie/donut chart."

        elif any(k in (question or "").lower() for k in ["area chart"]):
            visualization = "area_chart"
            chart_type = "area_chart"
            rendered_component = "AreaChart"
            reason = "User explicitly requested an area chart."

        # 2. Single-scalar KPI Card (renders with embedded Sparkline)
        elif rc == 1 and cc == 1:
            visualization = "kpi_card"
            chart_type = "kpi_card"
            rendered_component = "KPICard"
            reason = "Single aggregate metric value."

        # 3. Single Row Multi-KPI
        elif rc == 1 and len(num_cols) >= 2 and len(cat_cols) == 0:
            visualization = "multi_kpi"
            chart_type = "multi_kpi"
            rendered_component = "MultiKPICards"
            reason = "Multiple scalar numeric metrics."

        # 4. Single Row Detail Card
        elif rc == 1 and cc > 1:
            visualization = "detail_card"
            chart_type = "detail_card"
            rendered_component = "DetailCard"
            reason = "Single entity detail card."

        # -------------------------------------------------------------
        # HIGH PRIORITY: Specialized Semantic Visualizations
        # -------------------------------------------------------------

        # 5. Funnel Chart (Conversion, Pipelines, Drop-offs, Stages)
        elif any(kw in (question or "").lower() for kw in ["funnel", "conversion", "dropoff", "drop-off", "pipeline", "stage", "checkout flow", "step"]) and len(num_cols) > 0 and 2 <= rc <= 15:
            visualization = "funnel_chart"
            chart_type = "funnel_chart"
            rendered_component = "FunnelChart"
            reason = "Sequential conversion pipeline & drop-off analysis."

        # 6. Heatmap Grid (2D Matrix: Day vs Hour, Category vs Region)
        elif any(kw in (question or "").lower() for kw in ["heatmap", "density", "matrix", "hour of day", "day of week", "busiest time", "peak hour", "intensity"]) and (len(cat_cols) + len(time_cols) >= 2) and 4 <= rc <= 250:
            visualization = "heatmap"
            chart_type = "heatmap"
            rendered_component = "Heatmap"
            reason = "Two-dimensional matrix density distribution."

        # 7. Treemap (Hierarchical Category Area Mapping)
        elif any(kw in (question or "").lower() for kw in ["treemap", "hierarchical", "nested", "allocation", "portfolio", "budget breakdown", "sub-category", "breakdown"]) and len(cat_cols) >= 1 and rc >= 3:
            visualization = "treemap"
            chart_type = "treemap"
            rendered_component = "Treemap"
            reason = "Hierarchical proportional area distribution."

        # 8. Gantt Chart (Task Schedules & Workflow Durations)
        elif any(kw in (question or "").lower() for kw in ["gantt", "schedule", "milestone", "timeline", "lead time", "task duration", "roadmap"]) and len(num_cols) > 0 and rc >= 2:
            visualization = "gantt_chart"
            chart_type = "gantt_chart"
            rendered_component = "GanttChart"
            reason = "Task schedule and milestone duration timeline."

        # 9. Geographic / Regional Map Plot
        elif (bool(re.search(r"\b(map|maps|geography|regional|country|state|city|location|locations|territory|worldwide)\b", (question or "").lower())) or any(re.search(r"\b(country|state|city|region|territory|zip_code|latitude|longitude)\b", c, re.I) for c in cols)) and len(num_cols) > 0 and 2 <= rc <= 250:
            visualization = "geo_map"
            chart_type = "geo_map"
            rendered_component = "GeoMap"
            reason = "Geographic regional distribution and spatial concentration."

        # 10. Pareto 80/20 Chart
        elif any(kw in (question or "").lower() for kw in ["pareto", "80/20", "cumulative share", "cumulative percentage", "top contributor"]) and len(num_cols) > 0 and rc >= 3:
            visualization = "pareto_chart"
            chart_type = "pareto_chart"
            rendered_component = "ParetoChart"
            reason = "80/20 Pareto distribution & cumulative percentage analysis."

        # 11. Scatter Chart (Multi-metric correlation)
        elif (len(num_cols) >= 2 or any(kw in (question or "").lower() for kw in ["scatter", "correlation", "relationship", "vs", "versus"])) and len(num_cols) >= 2 and rc >= 4:
            visualization = "scatter_chart"
            chart_type = "scatter_chart"
            rendered_component = "ScatterPlot"
            reason = "Multi-variable numeric correlation & scatter distribution."

        # -------------------------------------------------------------
        # STANDARD VISUALIZATIONS & FALLBACKS
        # -------------------------------------------------------------

        # 12. Percentage / Share -> Pie Chart
        elif (len(pct_cols) > 0 or any(kw in (question or "").lower() for kw in ["percentage", "share", "distribution", "proportion"])) and 2 <= rc <= 10:
            visualization = "pie_chart"
            chart_type = "pie_chart"
            rendered_component = "PieChart"
            reason = "Proportional categorical breakdown."

        # 13. Time-Series Trend -> Line Chart
        elif len(time_cols) > 0 and len(num_cols) > 0 and rc > 1:
            visualization = "line_chart"
            chart_type = "line_chart"
            rendered_component = "LineChart"
            reason = "Time-series trend analysis."

        # 14. Top-N Ranking (ORDER BY + LIMIT) -> Horizontal Leaderboard / Bar
        elif is_top_n and rc > 1:
            visualization = "horizontal_bar"
            chart_type = "horizontal_bar"
            rendered_component = "Leaderboard"
            reason = "Top-N ranked entity breakdown."

        # 15. Standard Categorical Comparison -> Bar Chart
        elif len(cat_cols) > 0 and len(num_cols) > 0 and rc > 1:
            visualization = "bar_chart"
            chart_type = "bar_chart"
            rendered_component = "BarChart"
            reason = "Categorical metric comparison."

        # 16. Wide datasets fallback
        elif rc > 40 or cc > 5:
            visualization = "table"
            chart_type = "table"
            rendered_component = "DataGrid"
            reason = "Large or wide dataset default to paginated table."

        # 17. General multi-column fallback
        elif rc > 1 and cc >= 2:
            visualization = "bar_chart"
            chart_type = "bar_chart"
            rendered_component = "BarChart"
            reason = "Categorical metric comparison."


        log.info(
            "visualization_decision",
            question=question[:50],
            sql=sql[:50],
            row_count=rc,
            column_names=cols,
            column_types=profile["column_types"],
            recommended_vis=visualization,
            reason=reason,
            rendered_component=rendered_component
        )

        return {
            "visualization": visualization,
            "chart_type": chart_type,
            "title": title,
            "confidence_score": 1.0,
            "rows": rows,
            "columns": cols,
            "profile": profile,
            "reason": reason,
            "rendered_component": rendered_component
        }

    @staticmethod
    def recommend(data_or_plan: Any, row_count: int = 0, column_count: int = 0, as_dict: bool = False, question: str = "") -> Any:
        """Backward-compatible recommendation helper."""
        if isinstance(data_or_plan, list):
            cols = list(data_or_plan[0].keys()) if len(data_or_plan) > 0 and isinstance(data_or_plan[0], dict) else []
            res = ChartRecommender.recommend_visualization(data_or_plan, cols, question=question)
            return res if as_dict else res["visualization"]

        res = {"visualization": "table", "chart_type": "table", "title": "Query Results", "reason": "Query results."}
        return res if as_dict else res["visualization"]
