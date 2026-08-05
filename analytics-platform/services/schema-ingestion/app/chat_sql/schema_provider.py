"""Schema Provider.

Loads active database schema dynamically from SchemaRegistry for Ask AI workflow.
Does NOT require hardcoded file paths or application restarts.
"""
from pathlib import Path
from typing import Any, Optional, Tuple
import structlog

from app.models import DataSource, SchemaRegistry

log = structlog.get_logger(__name__)

FALLBACK_SCHEMA_FILE = r"C:\Users\Admin\Downloads\Analytics_Database_Schema.txt"


class SchemaProvider:
    """Provides active database schema text dynamically for Ask AI workflow."""

    def __init__(self, fallback_file: Optional[str] = None):
        self.fallback_file = fallback_file

    @staticmethod
    def _load_schema_from_path(file_path: str) -> str:
        """Loads schema file text with UTF-8 encoding, verifying file existence."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Schema file not found: {file_path}")
        return path.read_text(encoding="utf-8")

    def get_connected_schema(
        self,
        db_session: Optional[Any] = None,
        user: Optional[Any] = None,
        source: Optional[DataSource] = None
    ) -> Tuple[str, str]:
        """Dynamically fetches active schema from SchemaRegistry or active DataSource.
        
        Returns (database_name, schema_text).
        """
        # 1. Try active SchemaRegistry lookup via db_session
        if db_session:
            try:
                target_source_id = source.id if source else None
                if not target_source_id and user and hasattr(user, "tenant_id"):
                    active_src = db_session.query(DataSource).filter_by(
                        tenant_id=user.tenant_id,
                        status="connected"
                    ).first()
                    if active_src:
                        target_source_id = active_src.id

                # Global fallback to any connected DataSource if user context is missing
                if not target_source_id:
                    active_src = db_session.query(DataSource).filter_by(status="connected").first()
                    if active_src:
                        target_source_id = active_src.id

                if target_source_id:
                    active_registry = db_session.query(SchemaRegistry).filter_by(
                        source_id=target_source_id,
                        is_active=True
                    ).first()

                    if active_registry and Path(active_registry.file_path).exists():
                        log.info(
                            "dynamic_schema_loaded_from_registry",
                            source_id=str(target_source_id),
                            version=active_registry.schema_version,
                            path=active_registry.file_path
                        )
                        schema_text = self._load_schema_from_path(active_registry.file_path)
                        return active_registry.database_name, schema_text
            except Exception as exc:
                log.warning("failed_to_load_active_schema_from_registry", error=str(exc))

        # 2. Check explicitly provided fallback file if specified
        try:
            if self.fallback_file and Path(self.fallback_file).exists():
                schema_text = self._load_schema_from_path(self.fallback_file)
                return "analytics_db", schema_text
        except Exception:
            pass

        # 3. Dynamic schema fallback via DynamicSchemaService
        try:
            from app.services.dynamic_schema_service import DynamicSchemaService
            schema_info = DynamicSchemaService().get_schema()
            return schema_info.get("database_name", "analytics_db"), schema_info.get("formatted_ddl", "")
        except Exception as exc:
            log.error("dynamic_schema_fallback_failed", error=str(exc))
            return "analytics_db", ""


