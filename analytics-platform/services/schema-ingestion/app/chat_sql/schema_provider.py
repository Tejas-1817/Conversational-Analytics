"""Schema Provider.

Loads static schema file directly using pathlib.Path with UTF-8 encoding.
Does NOT use DynamicSchemaService or dynamic DB introspection for Ask AI.
"""
from pathlib import Path
from typing import Tuple
import structlog

log = structlog.get_logger(__name__)

DEFAULT_SCHEMA_FILE = r"C:\Users\Admin\Downloads\Analytics_Database_Schema.txt"


class SchemaProvider:
    """Provides static database schema text for Ask AI workflow."""

    def __init__(self, schema_file: str = DEFAULT_SCHEMA_FILE):
        self.schema_file = schema_file

    @staticmethod
    def _load_schema(schema_file: str) -> str:
        """Loads static schema file text with UTF-8 encoding, verifying file existence."""
        path = Path(schema_file)
        if not path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_file}")
        return path.read_text(encoding="utf-8")

    def get_connected_schema(self) -> Tuple[str, str]:
        """Returns (database_name, schema_text)."""
        schema_text = self._load_schema(self.schema_file)
        return "analytics_db", schema_text

