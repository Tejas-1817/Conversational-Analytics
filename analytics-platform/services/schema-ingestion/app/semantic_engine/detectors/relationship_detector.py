"""Deterministic Relationship Detector.

Detects 1:1, 1:N, N:1, and N:N relationships using Foreign Keys,
Primary Keys, and Unique Constraints extracted from database metadata.
"""
from typing import Any, Dict, List


class RelationshipDetector:
    """Pure Python rule engine for relationship cardinality inference."""

    def detect_relationships(self, catalog: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Inspect catalog tables and FK definitions to determine cardinalities.

        - ONE_TO_ONE: Source FK is a Primary Key or uniquely constrained.
        - MANY_TO_ONE: Standard FK pointing from Source -> Target PK.
        - ONE_TO_MANY: Inverted view of MANY_TO_ONE.
        - MANY_TO_MANY: Junction/bridge table containing 2+ FKs.
        """
        relationships: List[Dict[str, Any]] = []
        tables = catalog.get("tables", {})

        # Track table FK counts for Many-to-Many junction table detection
        table_fk_counts: Dict[str, int] = {}
        for table_name, table_info in tables.items():
            fks = table_info.get("foreign_keys", [])
            table_fk_counts[table_name] = len(fks)

        for table_name, table_info in tables.items():
            pk_cols = set(table_info.get("primary_keys", []))
            unique_cols = set(table_info.get("unique_constraints", []))
            fks = table_info.get("foreign_keys", [])

            is_junction_table = (
                len(fks) >= 2
                and len(table_info.get("columns", {})) <= len(fks) + 2
            )

            for fk in fks:
                source_col = fk.get("constrained_columns", [""])[0] if fk.get("constrained_columns") else ""
                target_table = fk.get("referred_table", "")
                target_col = fk.get("referred_columns", [""])[0] if fk.get("referred_columns") else ""

                if not source_col or not target_table:
                    continue

                if is_junction_table:
                    rel_type = "MANY_TO_MANY"
                elif source_col in pk_cols or source_col in unique_cols:
                    rel_type = "ONE_TO_ONE"
                else:
                    rel_type = "MANY_TO_ONE"

                relationships.append({
                    "source_table": table_name,
                    "source_column": source_col,
                    "target_table": target_table,
                    "target_column": target_col,
                    "relationship_type": rel_type,
                    "status": "Draft"
                })

        return relationships
