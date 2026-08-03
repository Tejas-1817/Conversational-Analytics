"""Deterministic Metric Detector.

Detects numeric measures (int, decimal, float, numeric) and generates
aggregation suggestions (SUM, AVG, COUNT, MIN, MAX) based on heuristics.
"""
import re
from typing import Any, Dict, List

NUMERIC_TYPES = ["int", "bigint", "integer", "numeric", "decimal", "float", "double", "real"]

# Measures that suggest additive SUM metrics
ADDITIVE_PATTERNS = [
    r".*sales.*", r".*revenue.*", r".*amount.*", r".*price.*", r".*salary.*",
    r".*profit.*", r".*cost.*", r".*discount.*", r".*quantity.*", r".*fee.*",
    r".*total.*", r".*balance.*", r".*score.*"
]


class MetricDetector:
    """Pure Python rule engine for candidate metric detection."""

    def detect_metrics(self, catalog: Dict[str, Any]) -> List[Dict[str, Any]]:
        metrics: List[Dict[str, Any]] = []
        tables = catalog.get("tables", {})

        for table_name, table_info in tables.items():
            schema_name = table_info.get("schema_name", "public")
            columns = table_info.get("columns", {})
            pk_cols = set(table_info.get("primary_keys", []))
            fk_cols = {
                fk.get("constrained_columns", [""])[0]
                for fk in table_info.get("foreign_keys", [])
                if fk.get("constrained_columns")
            }

            for col_name, col_meta in columns.items():
                # Skip PK and FK columns from being raw sum metrics
                if col_name in pk_cols or col_name in fk_cols:
                    continue

                data_type = str(col_meta.get("data_type", "")).lower()
                is_numeric = any(n in data_type for n in NUMERIC_TYPES)

                if is_numeric:
                    clean_name = col_name.replace("_", " ").title()
                    is_additive = any(re.match(p, col_name.lower()) for p in ADDITIVE_PATTERNS)

                    if is_additive:
                        aggregations = [
                            ("Total " + clean_name, "SUM", f"SUM({col_name})"),
                            ("Average " + clean_name, "AVG", f"AVG({col_name})"),
                            ("Maximum " + clean_name, "MAX", f"MAX({col_name})"),
                            ("Minimum " + clean_name, "MIN", f"MIN({col_name})")
                        ]
                    else:
                        aggregations = [
                            ("Average " + clean_name, "AVG", f"AVG({col_name})"),
                            ("Maximum " + clean_name, "MAX", f"MAX({col_name})"),
                            ("Minimum " + clean_name, "MIN", f"MIN({col_name})")
                        ]

                    for m_name, agg_type, expr in aggregations:
                        metrics.append({
                            "schema_name": schema_name,
                            "table_name": table_name,
                            "column_name": col_name,
                            "metric_name": m_name,
                            "aggregation_type": agg_type,
                            "expression": expr,
                            "status": "Draft"
                        })

        return metrics
