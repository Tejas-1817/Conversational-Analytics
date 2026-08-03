"""Deterministic Dimension Detector.

Detects categorical, boolean, enum, and text dimensions based on data types
and column naming conventions (e.g., name, city, state, category, status).
"""
import re
from typing import Any, Dict, List

DIMENSION_TYPES = {
    "varchar": "CATEGORICAL",
    "text": "CATEGORICAL",
    "char": "CATEGORICAL",
    "string": "CATEGORICAL",
    "uuid": "UUID",
    "boolean": "BOOLEAN",
    "bool": "BOOLEAN",
    "enum": "ENUM",
}

DIMENSION_NAME_PATTERNS = [
    r".*name.*", r".*city.*", r".*state.*", r".*country.*", r".*department.*",
    r".*category.*", r".*brand.*", r".*status.*", r".*gender.*", r".*store.*",
    r".*type.*", r".*role.*", r".*code.*", r".*address.*", r".*region.*",
    r".*segment.*", r".*title.*", r".*description.*"
]


class DimensionDetector:
    """Pure Python rule engine for candidate dimension detection."""

    def detect_dimensions(self, catalog: Dict[str, Any]) -> List[Dict[str, Any]]:
        dimensions: List[Dict[str, Any]] = []
        tables = catalog.get("tables", {})

        for table_name, table_info in tables.items():
            schema_name = table_info.get("schema_name", "public")
            columns = table_info.get("columns", {})

            for col_name, col_meta in columns.items():
                data_type = str(col_meta.get("data_type", "")).lower()

                # Rule 1: Direct data type matching
                dim_type = None
                for type_key, mapped_type in DIMENSION_TYPES.items():
                    if type_key in data_type:
                        dim_type = mapped_type
                        break

                # Rule 2: Pattern matching for string-like or ID columns
                if not dim_type:
                    for pattern in DIMENSION_NAME_PATTERNS:
                        if re.match(pattern, col_name.lower()):
                            dim_type = "CATEGORICAL"
                            break

                if dim_type:
                    dimension_name = col_name.replace("_", " ").title()
                    dimensions.append({
                        "schema_name": schema_name,
                        "table_name": table_name,
                        "column_name": col_name,
                        "dimension_name": dimension_name,
                        "dimension_type": dim_type,
                        "status": "Draft"
                    })

        return dimensions
