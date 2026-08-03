"""Schema Provider.

Retrieves introspected database DDL and catalog metadata directly
from the currently connected PostgreSQL database via DynamicSchemaService.
NEVER uses static schema files.
"""
from typing import Any, Dict, Tuple

from app.services.dynamic_schema_service import DynamicSchemaService


class SchemaProvider:
    """Provides live connected PostgreSQL database schema and metadata."""

    def __init__(self):
        self.schema_service = DynamicSchemaService()

    def get_connected_schema(self) -> Tuple[str, str, Dict[str, Any]]:
        """Returns (database_name, combined_ddl, catalog_dict)."""
        schema_info = self.schema_service.get_schema()
        db_name = schema_info.get("database_name", "analytics_db")
        ddl = schema_info.get("ddl", "")
        catalog = schema_info.get("catalog", {}).get("tables", {})

        if not catalog and "schema_metadata" in schema_info:
            catalog = {
                t: {"columns": {c: {} for c in cols}}
                for t, cols in schema_info["schema_metadata"].get("tables", {}).items()
            }

        return db_name, ddl, catalog
