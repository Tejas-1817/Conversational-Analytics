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


def export_human_readable_schema(session: Session, source: DataSource) -> Dict[str, Any]:
    """Generates human-readable .txt schema file, updates SchemaRegistry, and tracks IngestionJob."""
    start_time = datetime.now(timezone.utc)
    
    tenant_str = str(source.tenant_id)
    source_str = str(source.id)
    
    # 1. Target directory under storage/schemas/{tenant_id}/{source_id}/
    target_dir = Path("storage") / "schemas" / tenant_str / source_str
    target_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp_str = start_time.strftime("%Y%m%d_%H%M%S")
    txt_filename = f"schema_{timestamp_str}.txt"
    filepath = target_dir / txt_filename
    
    # 2. Extract DDL text for all non-system business tables
    from app.services.dynamic_schema_service import _SYSTEM_TABLES
    tables = session.query(TableMeta).filter(
        TableMeta.source_id == source.id,
        TableMeta.is_active == True,
        ~TableMeta.table_name.in_(_SYSTEM_TABLES)
    ).order_by(TableMeta.table_name).all()
    
    lines = [f"Database Name: {source.database_name}\n"]
    for t in tables:
        lines.append(f"TABLE: {t.table_name}")
        cols = session.query(ColumnMeta).filter_by(table_id=t.id, is_active=True).order_by(ColumnMeta.ordinal_position).all()
        for c in cols:
            flags = []
            if getattr(c, "is_primary_key", False):
                flags.append("PK")
            if not c.is_nullable:
                flags.append("NOT NULL")
            flag_str = f", {', '.join(flags)}" if flags else ""
            lines.append(f"- {c.column_name} ({c.data_type}{flag_str})")
        lines.append("")  # Empty spacer line
    
    schema_text = "\n".join(lines).strip()
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(schema_text)
    
    # 3. Update Schema Registry (Deactivate previous, Activate newest)
    from app.models import SchemaRegistry, IngestionJob, Base
    from app.db import get_engine
    try:
        Base.metadata.create_all(bind=get_engine(), tables=[SchemaRegistry.__table__])
    except Exception as exc:
        log.warning("schema_registries_table_creation_warning", error=str(exc))

    previous_entries = session.query(SchemaRegistry).filter_by(source_id=source.id, is_active=True).all()
    for prev in previous_entries:
        prev.is_active = False
    
    latest_reg = session.query(SchemaRegistry).filter_by(source_id=source.id).order_by(SchemaRegistry.schema_version.desc()).first()
    next_version = (latest_reg.schema_version + 1) if latest_reg else 1
    
    new_registry = SchemaRegistry(
        tenant_id=source.tenant_id,
        source_id=source.id,
        database_name=source.database_name,
        schema_version=next_version,
        file_path=str(filepath),
        is_active=True
    )
    session.add(new_registry)
    session.flush()
    
    finish_time = datetime.now(timezone.utc)
    duration_sec = round((finish_time - start_time).total_seconds(), 2)
    
    # 4. Record Ingestion Job
    job = IngestionJob(
        source_id=source.id,
        stage="Schema Extraction",
        status="succeeded",
        started_at=start_time,
        finished_at=finish_time,
        stats={
            "schema_version": next_version,
            "file_path": str(filepath),
            "table_count": len(tables),
            "duration_sec": duration_sec,
            "download_url": f"/api/v1/schemas/{new_registry.id}/download"
        }
    )
    session.add(job)
    session.commit()
    
    log.info(
        "human_readable_schema_exported",
        source=source.name,
        version=next_version,
        path=str(filepath),
        tables=len(tables)
    )
    
    return {
        "status": "succeeded",
        "schema_id": str(new_registry.id),
        "version": next_version,
        "file_path": str(filepath),
        "table_count": len(tables)
    }

