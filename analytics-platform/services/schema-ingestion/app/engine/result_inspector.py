"""Result Inspector — Dataset Profiling & Column Type Classification Engine."""
import re
from typing import Any, Dict, List


class ResultInspector:
    """Profiles query result datasets and classifies column data types."""

    @staticmethod
    def profile_dataset(rows: List[Dict[str, Any]], columns: List[str] = None, sql: str = "") -> Dict[str, Any]:
        """Profiles rows and column data types into NUMERIC, CATEGORICAL, TIME_SERIES, PERCENTAGE."""
        rc = len(rows) if isinstance(rows, list) else 0
        cols = columns or (list(rows[0].keys()) if rc > 0 and isinstance(rows[0], dict) else [])
        cc = len(cols)

        column_types: Dict[str, str] = {}
        numeric_cols: List[str] = []
        categorical_cols: List[str] = []
        time_cols: List[str] = []
        percentage_cols: List[str] = []

        sql_upper = (sql or "").upper()
        is_top_n = "ORDER BY" in sql_upper and "LIMIT" in sql_upper
        is_aggregate = any(fn in sql_upper for fn in ["COUNT(", "SUM(", "AVG(", "MAX(", "MIN("])

        for col in cols:
            sample_vals = [r.get(col) for r in rows[:10] if r.get(col) is not None]
            col_lower = col.lower()

            # Check for percentage / share / rate
            has_percent_symbol = any("%" in str(v) for v in sample_vals)
            if has_percent_symbol or any(k in col_lower for k in ["percentage", "share", "pct", "rate", "ratio"]):
                column_types[col] = "PERCENTAGE"
                percentage_cols.append(col)
                numeric_cols.append(col)
                continue

            # Check for date / time / timestamp / month / year
            is_date_col = any(k in col_lower for k in ["date", "time", "timestamp", "month", "year", "day", "quarter"])
            sample_date_str = any(isinstance(v, str) and (re.search(r"^\d{4}-\d{2}", v) or re.search(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", v, re.IGNORECASE)) for v in sample_vals)
            if is_date_col or sample_date_str:
                column_types[col] = "TIME_SERIES"
                time_cols.append(col)
                continue

            # Check for numeric
            all_numeric = sample_vals and all(isinstance(v, (int, float)) or (isinstance(v, str) and v.replace(".", "", 1).isdigit()) for v in sample_vals)
            if all_numeric:
                column_types[col] = "NUMERIC"
                numeric_cols.append(col)
                continue

            # Categorical default
            column_types[col] = "CATEGORICAL"
            categorical_cols.append(col)

        return {
            "row_count": rc,
            "column_count": cc,
            "columns": cols,
            "column_types": column_types,
            "numeric_columns": numeric_cols,
            "categorical_columns": categorical_cols,
            "time_columns": time_cols,
            "percentage_columns": percentage_cols,
            "is_top_n": is_top_n,
            "is_aggregate": is_aggregate
        }
