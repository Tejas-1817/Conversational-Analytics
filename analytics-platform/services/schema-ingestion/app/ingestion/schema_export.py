"""Schema snapshot exporter.

Serializes schema metadata (tables, columns, types, PK/FK, roles, relationships)
to versioned JSON files under SCHEMA_SNAPSHOT_DIR for auditability and diffing.
Ensures sample values pass through PII masking before writing to disk.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
import structlog
from sqlalchemy.orm import Session

from app.config import get_settings
from app.ingestion.pii import mask_samples
from app.models import ColumnMeta, DataSource, MetadataVersion, Relationship, TableMeta

log = structlog.get_logger(__name__)


def export_schema_snapshot(
    session: Session,
    source: DataSource,
    version: MetadataVersion,
    stage_name: str = "export_snapshot"
) -> Dict[str, Any]:
    """Serializes schema snapshot to a versioned JSON file."""
    settings = get_settings()
    snapshot_base_dir = Path(settings.schema_snapshot_dir)
    
    tenant_str = str(source.tenant_id)
    source_str = str(source.id)
    version_num = version.version_number
    
    target_dir = snapshot_base_dir / tenant_str / source_str
    target_dir.mkdir(parents=True, exist_ok=True)
    
    snapshot_filename = f"v{version_num}.json"
    filepath = target_dir / snapshot_filename

    # Fetch tables for this source
    tables = session.query(TableMeta).filter_by(source_id=source.id, is_active=True).all()
    
    tables_data = []
    table_ids = [t.id for t in tables]
    
    for t in tables:
        cols = session.query(ColumnMeta).filter_by(table_id=t.id, is_active=True).all()
        cols_data = []
        for c in cols:
            profile_dict = c.profile if isinstance(c.profile, dict) else {}
            sample_vals = profile_dict.get("sample_values") or profile_dict.get("top_values") or []
            masked_samples = mask_samples(c.column_name, sample_vals) if sample_vals else []
            cols_data.append({
                "column_id": str(c.id),
                "column_name": c.column_name,
                "data_type": c.data_type,
                "is_nullable": c.is_nullable,
                "is_pk": getattr(c, "is_primary_key", False),
                "role": str(c.role) if c.role else "unknown",
                "sample_values": masked_samples
            })
            
        tables_data.append({
            "table_id": str(t.id),
            "schema_name": t.schema_name,
            "table_name": t.table_name,
            "business_name": t.business_name,
            "description": t.description,
            "columns": cols_data
        })

    # Fetch relationships for these tables
    relationships_data = []
    if table_ids:
        rels = session.query(Relationship).join(
            ColumnMeta, Relationship.from_column_id == ColumnMeta.id
        ).filter(ColumnMeta.table_id.in_(table_ids)).all()

        for r in rels:
            relationships_data.append({
                "relationship_id": str(r.id),
                "from_column_id": str(r.from_column_id),
                "to_column_id": str(r.to_column_id),
                "cardinality": r.cardinality,
                "source": str(r.source),
                "confidence": float(r.confidence) if r.confidence is not None else 1.0,
                "status": str(r.status)
            })

    snapshot_payload = {
        "tenant_id": tenant_str,
        "source_id": source_str,
        "source_name": source.name,
        "version_number": version_num,
        "stage": stage_name,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "tables": tables_data,
        "relationships": relationships_data
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(snapshot_payload, f, indent=2)

    log.info("schema_snapshot_exported", path=str(filepath), tables=len(tables_data), version=version_num)

    return {
        "status": "succeeded",
        "snapshot_path": str(filepath),
        "tables_exported": len(tables_data),
        "relationships_exported": len(relationships_data)
    }
