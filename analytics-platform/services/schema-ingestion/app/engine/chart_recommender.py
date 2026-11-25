"""Chart Recommender — Deterministic Enterprise Visualization Recommendation Engine."""
import re
import structlog
from typing import Any, Dict, List, Optional
from app.engine.result_inspector import ResultInspector

log = structlog.get_logger(__name__)

CAROUSEL_MAX_CARDS = 10
PIE_MAX_SLICES = 7


def _format_col(col: str, is_dim: bool = False) -> str:
    """Formats column names into human-readable business titles."""
    c = col.strip()
    if is_dim:
        cleaned = re.sub(r"_(name|id|code|pk|fk|uuid)$", "", c, flags=re.IGNORECASE)
        if len(cleaned) >= 2:
            c = cleaned
    parts = c.replace("_", " ").replace("-", " ").split()
    capitalized = []
    acronyms = {"id": "ID", "kpi": "KPI", "mrr": "MRR", "arr": "ARR", "sla": "SLA", "url": "URL", "api": "API", "sku": "SKU", "sql": "SQL"}
    for p in parts:
        low = p.lower()
        if low in acronyms:
            capitalized.append(acronyms[low])
        else:
            capitalized.append(p.capitalize())
    return " ".join(capitalized)


def _infer_title(question: str, columns: List[str], visualization: str, profile: Optional[Dict[str, Any]] = None) -> str:
    """Infers Pattern A data-driven title ('[Metric 1] & [Metric 2] by [Dimension]') from dataset metadata."""
    if not columns and not profile:
        return "Query Results"

    cols = columns or (profile.get("columns", []) if profile else [])
    num_cols = list(profile.get("numeric_columns", [])) if profile else []
    cat_cols = list(profile.get("categorical_columns", [])) if profile else []
    time_cols = list(profile.get("time_columns", [])) if profile else []

    # If profile was not provided, categorize heuristically from column names
    if not profile and cols:
        for c in cols:
            low = c.lower()
            if any(k in low for k in ["date", "time", "timestamp", "month", "year", "day", "quarter"]):
                time_cols.append(c)
            elif any(k in low for k in ["count", "sum", "total", "amount", "revenue", "cost", "price", "score", "rate", "pct", "risk", "num", "value", "quantity"]):
                num_cols.append(c)
            else:
                cat_cols.append(c)

    # Filter out pure ID columns from metrics
    pure_metrics = [c for c in num_cols if not re.search(r"(_id|id|_pk|_fk|_uuid)$", c, re.IGNORECASE)]
    if not pure_metrics and num_cols:
        pure_metrics = num_cols

    # Primary Dimension: prefer categorical unless time series visualization
    primary_dim = None
    is_time_dim = False
    if visualization in ["line_chart", "area_chart"] and time_cols:
        primary_dim = time_cols[0]
        is_time_dim = True
    elif cat_cols:
        primary_dim = cat_cols[0]
    elif time_cols:
        primary_dim = time_cols[0]
        is_time_dim = True

    # Construct Metric part
    if pure_metrics:
        if len(pure_metrics) == 1:
            metric_part = _format_col(pure_metrics[0])
        elif len(pure_metrics) == 2:
            metric_part = f"{_format_col(pure_metrics[0])} & {_format_col(pure_metrics[1])}"
        else:
            metric_part = f"{_format_col(pure_metrics[0])} & {_format_col(pure_metrics[1])}"
    else:
        metric_part = _format_col(cols[0]) if cols else "Query Results"

    # Construct Pattern A: "[Metric(s)] by/over [Dimension]"
    if primary_dim and primary_dim not in pure_metrics[:2]:
        dim_str = _format_col(primary_dim, is_dim=True)
        connector = "over" if is_time_dim else "by"
        return f"{metric_part} {connector} {dim_str}"

    return metric_part or "Query Results"


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
        title = _infer_title(question, cols, "", profile=profile)

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

        elif any(k in (question or "").lower() for k in ["combo", "dual axis", "dual-axis", "two axes", "secondary axis", "combo chart"]) and len(num_cols) >= 2:
            visualization = "combo"
            chart_type = "combo"
            rendered_component = "ComboChart"
            reason = "User explicitly requested a dual-axis combo chart."

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
        elif (len(num_cols) >= 2 or any(kw in (question or "").lower() for kw in ["scatter", "correlation", "relationship", "vs", "versus"])) and len(num_cols) >= 2 and rc >= 4 and not (len(cat_cols) > 0 or len(time_cols) > 0):
            visualization = "scatter_chart"
            chart_type = "scatter_chart"
            rendered_component = "ScatterPlot"
            reason = "Multi-variable numeric correlation & scatter distribution."

        # 11b. Dual-scale measures comparison -> Combo (dual-axis) chart
        elif len(num_cols) >= 2 and (len(cat_cols) > 0 or len(time_cols) > 0) and 2 <= rc <= 50 and (
            (any(p in num_cols[0].lower() for p in ["pct", "percent", "margin", "rate", "ratio"]) != any(p in num_cols[1].lower() for p in ["pct", "percent", "margin", "rate", "ratio"]))
            or (
                max((abs(r.get(num_cols[1]) or 0) for r in rows), default=0) > 0
                and (
                    max((abs(r.get(num_cols[0]) or 0) for r in rows), default=0)
                    / max((abs(r.get(num_cols[1]) or 1) for r in rows), default=1)
                    >= 10.0
                )
            )
        ):
            visualization = "combo"
            chart_type = "combo"
            rendered_component = "ComboChart"
            reason = "Metrics detected on distinctly different numeric scales."

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

        # Compute Pattern A title using resolved visualization and profile
        title = _infer_title(question, cols, visualization, profile=profile)


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

        combo_spec = None
        if visualization == "combo" and len(num_cols) >= 2:
            x_col = time_cols[0] if time_cols else (cat_cols[0] if cat_cols else cols[0])
            c1_is_pct = any(p in num_cols[0].lower() for p in ["pct", "percent", "margin", "rate", "ratio"])
            c2_is_pct = any(p in num_cols[1].lower() for p in ["pct", "percent", "margin", "rate", "ratio"])
            combo_spec = {
                "schema_version": 1,
                "x_axis": x_col,
                "y_axes": [
                    {
                        "position": "left",
                        "series_type": "bar" if not c1_is_pct else "line",
                        "columns": [num_cols[0]],
                        "unit": "%" if c1_is_pct else None,
                    },
                    {
                        "position": "right",
                        "series_type": "line" if c2_is_pct else "bar",
                        "columns": [num_cols[1]],
                        "unit": "%" if c2_is_pct else None,
                    },
                ],
            }

        return {
            "visualization": visualization,
            "chart_type": chart_type,
            "title": title,
            "confidence_score": 1.0,
            "rows": rows,
            "columns": cols,
            "profile": profile,
            "reason": reason,
            "rendered_component": rendered_component,
            "combo_spec": combo_spec,
        }

    @staticmethod
    def infer_title(
        rows: Optional[List[Dict[str, Any]]] = None,
        columns: Optional[List[str]] = None,
        question: str = "",
        sql: str = ""
    ) -> str:
        """Universal title inference without requiring a full chart recommendation."""
        profile = None
        cols = columns or []
        if rows is not None and (columns or (len(rows) > 0 and isinstance(rows[0], dict))):
            c = columns or list(rows[0].keys())
            profile = ResultInspector.profile_dataset(rows, c, sql=sql)
            cols = profile.get("columns", c)
        return _infer_title(question, cols, "", profile=profile)

    @staticmethod
    def recommend(data_or_plan: Any, row_count: int = 0, column_count: int = 0, as_dict: bool = False, question: str = "") -> Any:
        """Backward-compatible recommendation helper supporting both datasets and LogicalQueryPlans."""
        if hasattr(data_or_plan, "chart_recommendation"):
            plan = data_or_plan
            if plan.chart_recommendation:
                return plan.chart_recommendation
            if row_count == 0 or (row_count == 1 and column_count <= 1 and len(getattr(plan, "dimension_ids", [])) == 0):
                return "kpi_card"
            if getattr(plan, "time_granularity", None) or getattr(plan, "time_intelligence", None):
                return "line_chart"
            dim_count = len(getattr(plan, "dimension_ids", []))
            if dim_count == 1 and 2 <= row_count <= PIE_MAX_SLICES:
                return "pie_chart"
            if (dim_count >= 2 or column_count > 3) and 2 <= row_count <= CAROUSEL_MAX_CARDS:
                return "carousel_cards"
            if dim_count == 1:
                return "bar_chart"
            return "table"

        if isinstance(data_or_plan, list):
            cols = list(data_or_plan[0].keys()) if len(data_or_plan) > 0 and isinstance(data_or_plan[0], dict) else []
            res = ChartRecommender.recommend_visualization(data_or_plan, cols, question=question)
            return res if as_dict else res["visualization"]

        res = {"visualization": "table", "chart_type": "table", "title": "Query Results", "reason": "Query results."}
        return res if as_dict else res["visualization"]
