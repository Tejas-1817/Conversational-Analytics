"""Database connector registry.

Connection creation currently lives in ``factory.py``. This module provides
supported-source validation and compatibility exports without referencing
adapter classes that have not been implemented.
"""

from __future__ import annotations

from app.connectors.factory import build_engine, verify_read_only


SUPPORTED_SOURCE_TYPES = frozenset(
    {
        "postgres",
        "mysql",
        "mssql",
        "excel",
    }
)


def normalize_source_type(source_type: str) -> str:
    """Validate and normalize a database source type."""
    normalized = source_type.strip().lower()

    if normalized not in SUPPORTED_SOURCE_TYPES:
        supported = ", ".join(sorted(SUPPORTED_SOURCE_TYPES))
        raise NotImplementedError(
            f"Source type {source_type!r} is not supported. "
            f"Supported types: {supported}."
        )

    return normalized


def is_supported(source_type: str) -> bool:
    """Return whether a source type is implemented."""
    return source_type.strip().lower() in SUPPORTED_SOURCE_TYPES


__all__ = [
    "SUPPORTED_SOURCE_TYPES",
    "build_engine",
    "verify_read_only",
    "normalize_source_type",
    "is_supported",
]