"""Dynamic Schema Introspection Service.

Inspects the connected PostgreSQL database using SQLAlchemy Inspection APIs and 
generates DDL schema definitions, table/column metadata maps, and count statistics
for Text-to-SQL prompt building and schema management.
"""
from datetime import datetime, timezone
import threading
from typing import Any, Dict, List, Optional, Set, Tuple
import structlog
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.db import get_engine

log = structlog.get_logger()

_SYSTEM_SCHEMAS = {"information_schema", "pg_catalog", "pg_toast", "mysql", "performance_schema", "sys"}


class DynamicSchemaService:
    """Singleton service that manages DB introspection, DDL generation, and caching."""

    def __init__(self):
        self._lock = threading.Lock()
        self._cache: Optional[Dict[str, Any]] = None

    def _introspect_database(self, engine: Engine) -> Dict[str, Any]:
        """Perform deep introspection using SQLAlchemy Inspector."""
        inspector = inspect(engine)
        db_name = engine.url.database or "postgresql"

        # Determine non-system schemas
        all_schemas = [s for s in inspector.get_schema_names() if s not in _SYSTEM_SCHEMAS]
        if not all_schemas:
            all_schemas = ["public"]

        ddl_statements: List[str] = []
        tables_metadata: Dict[str, List[str]] = {}
        
        table_count = 0
        column_count = 0
        relationship_count = 0

        log.info("schema_introspection_started", database=db_name, schemas=all_schemas)

        catalog_dict = {}
        for schema in all_schemas:
            try:
                table_names = inspector.get_table_names(schema=schema)
            except Exception as e:
                log.warning("schema_tables_fetch_error", schema=schema, error=str(e))
                continue

            for table_name in table_names:
                table_count += 1
                table_key = f"{schema}.{table_name}" if schema != "public" else table_name
                
                # Fetch columns
                columns = inspector.get_columns(table_name, schema=schema)
                pk_constraint = inspector.get_pk_constraint(table_name, schema=schema) or {}
                pk_cols = set(pk_constraint.get("constrained_columns") or [])

                # Fetch foreign keys (relationships)
                fks = inspector.get_foreign_keys(table_name, schema=schema) or []
                relationship_count += len(fks)

                col_defs: List[str] = []
                col_names: List[str] = []

                for col in columns:
                    column_count += 1
                    c_name = col["name"]
                    c_type = str(col["type"])
                    c_nullable = "" if col.get("nullable", True) else " NOT NULL"
                    c_default = f" DEFAULT {col['default']}" if col.get("default") is not None else ""
                    c_pk = " PRIMARY KEY" if c_name in pk_cols else ""

                    col_defs.append(f"    {c_name} {c_type}{c_pk}{c_nullable}{c_default}")
                    col_names.append(c_name)

                # Add FK definitions to DDL
                for fk in fks:
                    c_cols = ", ".join(fk.get("constrained_columns", []))
                    r_table = fk.get("referred_table", "")
                    r_schema = fk.get("referred_schema", "")
                    r_cols = ", ".join(fk.get("referred_columns", []))
                    target = f"{r_schema}.{r_table}" if r_schema and r_schema != "public" else r_table
                    
                    if c_cols and target and r_cols:
                        col_defs.append(f"    FOREIGN KEY ({c_cols}) REFERENCES {target}({r_cols})")

                ddl = f"CREATE TABLE {table_key} (\n" + ",\n".join(col_defs) + "\n);"
                ddl_statements.append(ddl)

                tables_metadata[table_name] = col_names
                if schema != "public":
                    tables_metadata[table_key] = col_names

                catalog_dict[table_name] = {
                    "schema_name": schema,
                    "columns": {col["name"]: {"data_type": str(col["type"]), "nullable": col.get("nullable", True)} for col in columns},
                    "primary_keys": list(pk_cols),
                    "foreign_keys": fks
                }

        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        combined_ddl = "\n\n".join(ddl_statements)

        log.info(
            "schema_introspection_completed",
            database=db_name,
            tables=table_count,
            columns=column_count,
            relationships=relationship_count
        )

        return {
            "database_name": db_name,
            "status": "Generated",
            "generated_at": generated_at,
            "table_count": table_count,
            "column_count": column_count,
            "relationship_count": relationship_count,
            "ddl": combined_ddl,
            "schema_metadata": {"tables": tables_metadata},
            "catalog": {"tables": catalog_dict}
        }

    def get_schema(self, engine: Optional[Engine] = None, force_refresh: bool = False) -> Dict[str, Any]:
        """Get cached schema metadata or generate if missing / forced."""
        with self._lock:
            if self._cache is not None and not force_refresh:
                return self._cache

            try:
                if engine is None:
                    engine = get_engine()

                self._cache = self._introspect_database(engine)
                return self._cache
            except Exception as e:
                log.warning("schema_introspection_failed_using_fallback", error=str(e))
                from poc_text_to_sql import SAMPLE_SCHEMA_DDL, SCHEMA_METADATA
                fallback_data = {
                    "database_name": "poc_text_to_sql",
                    "status": "Loaded (Static)",
                    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "table_count": len(SCHEMA_METADATA.get("tables", {})),
                    "column_count": sum(len(cols) for cols in SCHEMA_METADATA.get("tables", {}).values()),
                    "relationship_count": 3,
                    "ddl": SAMPLE_SCHEMA_DDL,
                    "schema_metadata": SCHEMA_METADATA
                }
                self._cache = fallback_data
                return self._cache

    def refresh_schema(self, engine: Optional[Engine] = None) -> Dict[str, Any]:
        """Force re-introspection of the connected database."""
        return self.get_schema(engine=engine, force_refresh=True)


# Global Singleton Instance
schema_service = DynamicSchemaService()
