"""Deterministic Time Dimension Detector.

Detects temporal columns (DATE, TIMESTAMP, created_at, order_date, etc.).
"""
import re
from typing import Any, Dict, List

TIME_DATA_TYPES = ["date", "timestamp", "timestamptz", "datetime", "time"]

TIME_NAME_PATTERNS = [
    r".*_at$", r".*_date$", r".*_time$", r".*_dt$", r"^date$", r"^timestamp$",
    r".*created.*", r".*updated.*", r".*invoice.*", r".*order.*", r".*birth.*"
]


class TimeDimensionDetector:
    """Pure Python rule engine for candidate time dimension detection."""

    def detect_time_dimensions(self, catalog: Dict[str, Any]) -> List[Dict[str, Any]]:
        time_dims: List[Dict[str, Any]] = []
        tables = catalog.get("tables", {})

        for table_name, table_info in tables.items():
            schema_name = table_info.get("schema_name", "public")
            columns = table_info.get("columns", {})

            for col_name, col_meta in columns.items():
                data_type = str(col_meta.get("data_type", "")).lower()

                is_time = any(t in data_type for t in TIME_DATA_TYPES)
                if not is_time:
                    is_time = any(re.match(p, col_name.lower()) for p in TIME_NAME_PATTERNS)

                if is_time:
                    time_dim_name = col_name.replace("_", " ").title()
                    time_dims.append({
                        "schema_name": schema_name,
                        "table_name": table_name,
                        "column_name": col_name,
                        "time_dimension_name": time_dim_name,
                        "status": "Draft"
                    })

        return time_dims
