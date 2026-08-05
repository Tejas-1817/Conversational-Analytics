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

        # Rule 9: 0 Rows
        if rc == 0:
            visualization = "table"
            chart_type = "table"
            rendered_component = "NoData"
            reason = "No matching records found."

        # Rule 8: Wide datasets (>20 rows or >4 columns) -> Table
        elif rc > 20 or cc > 4:
            visualization = "table"
            chart_type = "table"
            rendered_component = "DataGrid"
            reason = "Large or wide dataset default to paginated table."

        # Rule 1: 1 Row + 1 Numeric Column -> KPI Card
        elif rc == 1 and cc == 1:
            visualization = "kpi_card"
            chart_type = "kpi_card"
            rendered_component = "KPICard"
            reason = "Single aggregate metric value."

        # Rule 2: 1 Row + Multiple Numeric Columns -> Multi KPI Cards
        elif rc == 1 and len(num_cols) >= 2 and len(cat_cols) == 0:
            visualization = "multi_kpi"
            chart_type = "multi_kpi"
            rendered_component = "MultiKPICards"
            reason = "Multiple scalar numeric metrics."

        # Rule 3: 1 Row + Multiple Descriptive Columns -> Entity Detail Card
        elif rc == 1 and cc > 1:
            visualization = "detail_card"
            chart_type = "detail_card"
            rendered_component = "DetailCard"
            reason = "Single entity detail card."

        # Rule 4: Top-N Ranking (ORDER BY + LIMIT) -> Horizontal Leaderboard / Bar
        elif is_top_n and rc > 1:
            visualization = "horizontal_bar"
            chart_type = "horizontal_bar"
            rendered_component = "Leaderboard"
            reason = "Top-N ranked entity breakdown."

        # Rule 7: Category + Percentage / Share -> Pie Chart
        elif (len(pct_cols) > 0 or any(kw in (question or "").lower() for kw in ["percentage", "share", "distribution", "breakdown"])) and 2 <= rc <= 10:
            visualization = "pie_chart"
            chart_type = "pie_chart"
            rendered_component = "PieChart"
            reason = "Proportional categorical breakdown."

        # Rule 6: Date/Time + Numeric -> Line Chart
        elif len(time_cols) > 0 and len(num_cols) > 0 and rc > 1:
            visualization = "line_chart"
            chart_type = "line_chart"
            rendered_component = "LineChart"
            reason = "Time-series trend analysis."

        # Rule 5: Category + Numeric -> Bar Chart
        elif len(cat_cols) > 0 and len(num_cols) > 0 and rc > 1:
            visualization = "bar_chart"
            chart_type = "bar_chart"
            rendered_component = "BarChart"
            reason = "Categorical metric comparison."

        # General multi-column fallback
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
