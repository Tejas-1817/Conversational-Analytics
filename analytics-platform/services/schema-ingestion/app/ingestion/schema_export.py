"""Schema snapshot exporter.

Serializes schema metadata (tables, columns, types, PK/FK, roles, relationships)
to versioned JSON files under SCHEMA_SNAPSHOT_DIR for auditability and diffing.
Ensures sample values pass through PII masking before writing to disk.
"""
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
import structlog
from sqlalchemy.orm import Session

from app.config import get_settings
from app.ingestion.pii import mask_samples
from app.models import ColumnMeta, DataSource, MetadataVersion, Relationship, TableMeta

log = structlog.get_logger(__name__)

TABLE_PROMPT_TEMPLATE = """You are a database documentation assistant.
Convert the following SQL CREATE TABLE statement into a clear, plain-English
description. Describe the table's purpose (infer it from the name/columns if
not obvious), list each column with its type and any constraints (primary
key, foreign key, not null, default), in plain sentences — not SQL syntax.
Keep it concise. Do not include markdown code fences in your response.

SQL:
{sql}

Plain-text description:
"""


def _sanitize_slug(value: Any, fallback: str) -> str:
    """Sanitizes username or database_name strings for filesystem safety."""
    if not isinstance(value, str) or not value.strip():
        val_str = fallback
    else:
        val_str = value.strip()
    return re.sub(r'[<>:"/\\|?*]', '_', val_str)


def _secure_atomic_write(target_path: Path, content: str | bytes) -> str:
    """Writes content to a temporary file and atomically replaces target_path.
    
    Returns the SHA-256 hash digest of the content.
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.with_suffix(f"{target_path.suffix}.tmp.{uuid.uuid4().hex[:8]}")
    
    mode = "w" if isinstance(content, str) else "wb"
    encoding = "utf-8" if isinstance(content, str) else None
    with open(tmp_path, mode, encoding=encoding) as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
        
    data_bytes = content.encode("utf-8") if isinstance(content, str) else content
    sha256_hash = hashlib.sha256(data_bytes).hexdigest()
    
    os.replace(tmp_path, target_path)
    return sha256_hash


def export_schema_snapshot(
    session: Session,
    source: DataSource,
    version: MetadataVersion,
    stage_name: str = "export_snapshot",
    username: str | None = None,
) -> Dict[str, Any]:
    """Serializes schema snapshot to a versioned JSON file with atomic write and SHA-256 integrity digest."""
    settings = get_settings()
    snapshot_base_dir = Path(settings.schema_snapshot_dir)
    
    tenant_str = str(source.tenant_id)
    source_str = str(source.id)
    version_num = version.version_number
    
    user_slug = _sanitize_slug(username or getattr(source, "username", None), "admin")
    db_name = _sanitize_slug(getattr(source, "database_name", None) or getattr(source, "name", None), "analytics_db")
    base_name = f"{user_slug}_{db_name}_v{version_num}"
    
    target_dir = snapshot_base_dir / tenant_str / source_str
    target_dir.mkdir(parents=True, exist_ok=True)
    
    snapshot_filename = f"snapshot_{base_name}.json"
    filepath = target_dir / snapshot_filename
    legacy_filepath = target_dir / f"v{version_num}.json"

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

    json_content = json.dumps(snapshot_payload, indent=2)
    file_sha256 = _secure_atomic_write(filepath, json_content)
    _secure_atomic_write(legacy_filepath, json_content)

    log.info("schema_snapshot_exported", path=str(filepath), tables=len(tables_data), version=version_num, sha256=file_sha256)

    return {
        "status": "succeeded",
        "snapshot_path": str(filepath),
        "sha256": file_sha256,
        "tables_exported": len(tables_data),
        "relationships_exported": len(relationships_data)
    }


def export_human_readable_schema(
    session: Session,
    source: DataSource,
    username: str | None = None,
) -> Dict[str, Any]:
    """Generates enriched .sql schema file (with PK, FK, Metrics, Dimensions, Relationships & Glossary), updates SchemaRegistry, and tracks IngestionJob using versioned asset naming."""
    start_time = datetime.now(timezone.utc)
    settings = get_settings()
    
    tenant_str = str(source.tenant_id)
    source_str = str(source.id)
    
    # 1. Target directory under storage/schemas/{tenant_id}/{source_id}/
    target_dir = Path("storage") / "schemas" / tenant_str / source_str
    target_dir.mkdir(parents=True, exist_ok=True)

    # 2. Determine Schema Version
    from app.models import SchemaRegistry, IngestionJob, Base
    from app.db import get_engine
    try:
        Base.metadata.create_all(bind=get_engine(), tables=[SchemaRegistry.__table__])
    except Exception as exc:
        log.warning("schema_registries_table_creation_warning", error=str(exc))

    latest_reg = session.query(SchemaRegistry).filter_by(source_id=source.id).order_by(SchemaRegistry.schema_version.desc()).first()
    next_version = (latest_reg.schema_version + 1) if latest_reg else 1

    user_slug = _sanitize_slug(username or getattr(source, "username", None), "admin")
    db_name = _sanitize_slug(getattr(source, "database_name", None) or getattr(source, "name", None), "analytics_db")
    base_name = f"{user_slug}_{db_name}_v{next_version}"

    sql_filename = f"{base_name}.sql"
    json_summary_filename = f"embeddings_{base_name}.json"

    filepath = target_dir / sql_filename
    json_summary_filepath = target_dir / json_summary_filename

    # 3. Extract DDL text for all non-system business tables & relationships
    from app.services.dynamic_schema_service import _SYSTEM_TABLES
    tables = session.query(TableMeta).filter(
        TableMeta.source_id == source.id,
        TableMeta.is_active == True,
        ~TableMeta.table_name.in_(_SYSTEM_TABLES)
    ).order_by(TableMeta.table_name).all()
    
    table_ids = [t.id for t in tables]

    # Fetch relationships & map column metadata
    rels = []
    if table_ids:
        rels = session.query(Relationship).join(
            ColumnMeta, Relationship.from_column_id == ColumnMeta.id
        ).filter(ColumnMeta.table_id.in_(table_ids)).all()

    col_id_to_meta: Dict[uuid.UUID, tuple[str, str]] = {}
    for t in tables:
        cols = session.query(ColumnMeta).filter_by(table_id=t.id, is_active=True).all()
        for c in cols:
            col_id_to_meta[c.id] = (t.table_name, c.column_name)

    fk_map: Dict[uuid.UUID, tuple[str, str, str]] = {}
    for r in rels:
        if r.from_column_id in col_id_to_meta and r.to_column_id in col_id_to_meta:
            to_tbl, to_col = col_id_to_meta[r.to_column_id]
            fk_map[r.from_column_id] = (to_tbl, to_col, str(r.cardinality))

    lines = [f"-- Database Name: {source.database_name}\n"]
    glossary_lines = []

    for t in tables:
        lines.append(f"-- ==================================================")
        header_title = f"-- TABLE: {t.table_name}"
        if getattr(t, "business_name", None):
            header_title += f" (Business Name: {t.business_name})"
        lines.append(header_title)
        if getattr(t, "description", None):
            lines.append(f"-- Description: {t.description}")
        lines.append(f"-- ==================================================")
        lines.append(f"TABLE: {t.table_name}")

        cols = session.query(ColumnMeta).filter_by(table_id=t.id, is_active=True).order_by(ColumnMeta.ordinal_position).all()
        for c in cols:
            flags = []
            if getattr(c, "is_primary_key", False):
                flags.append("PK")
            if c.id in fk_map:
                to_tbl, to_col, _ = fk_map[c.id]
                flags.append(f"FK -> {to_tbl}.{to_col}")
            if not c.is_nullable:
                flags.append("NOT NULL")

            flag_str = f", {', '.join(flags)}" if flags else ""

            # Annotate Role (Metric/Dimension) & Aggregation
            role_str = str(c.role) if c.role else "unknown"
            comment_parts = [f"Role: {role_str}"]
            if getattr(c, "aggregation", None):
                comment_parts.append(f"Aggregation: {c.aggregation}")
            if getattr(c, "description", None):
                comment_parts.append(f"Desc: {c.description}")

            lines.append(f"- {c.column_name} ({c.data_type}{flag_str}) -- {' | '.join(comment_parts)}")

            # Collect Business Glossary metadata
            b_name = getattr(c, "business_name", None)
            syns = getattr(c, "synonyms", None) or []
            if b_name or syns:
                syn_str = f" | Synonyms: {', '.join(syns)}" if syns else ""
                term_name = b_name or c.column_name
                glossary_lines.append(f"- Term: {t.table_name}.{c.column_name} | Business Name: {term_name}{syn_str}")

        lines.append("")  # Spacer line

    # Append explicit Relationships Section
    if rels:
        lines.append("-- ==================================================")
        lines.append("-- TABLE RELATIONSHIPS & FOREIGN KEYS")
        lines.append("-- ==================================================")
        for r in rels:
            if r.from_column_id in col_id_to_meta and r.to_column_id in col_id_to_meta:
                f_tbl, f_col = col_id_to_meta[r.from_column_id]
                t_tbl, t_col = col_id_to_meta[r.to_column_id]
                lines.append(f"- FK: {f_tbl}.{f_col} -> {t_tbl}.{t_col} (Cardinality: {r.cardinality})")
        lines.append("")

    # Append Business Glossary Section
    if glossary_lines:
        lines.append("-- ==================================================")
        lines.append("-- BUSINESS GLOSSARY & SEMANTIC CONTEXT")
        lines.append("-- ==================================================")
        lines.extend(glossary_lines)
        lines.append("")

    schema_text = "\n".join(lines).strip()
    sql_sha256 = _secure_atomic_write(filepath, schema_text)

    # 3c. Automatically generate vector embeddings JSON from .sql schema text
    try:
        import re
        from app.embeddings.registry import get_embedding_provider

        raw_chunks = re.split(r"\n\s*\n", schema_text.strip())
        chunks = [c.strip() for c in raw_chunks if c.strip()]
        if not chunks and schema_text.strip():
            chunks = [schema_text.strip()]

        provider = get_embedding_provider()
        vectors = provider.embed(chunks)
        records = [
            {
                "id": f"chunk_{i}",
                "label": text.splitlines()[0][:80] if text else "",
                "text": text,
                "embedding": vector,
            }
            for i, (text, vector) in enumerate(zip(chunks, vectors))
        ]

        embed_payload_str = json.dumps({"model": settings.embedding_model, "records": records}, indent=2)
        embed_sha256 = _secure_atomic_write(json_summary_filepath, embed_payload_str)
        log.info("automatic_embeddings_json_generated", path=str(json_summary_filepath), records=len(records), sha256=embed_sha256)

        # 3d. Automatically store vector records into persistent ChromaDB vector collection
        try:
            from app.embeddings.chroma_store import ChromaStore, EmbeddedObject
            chroma_objects = [
                EmbeddedObject(
                    id=r["id"],
                    text=r["text"],
                    embedding=r["embedding"],
                    metadata={"label": r.get("label", ""), "tenant_id": tenant_str, "source_id": source_str}
                )
                for r in records
            ]
            upserted_count = ChromaStore().upsert(source.tenant_id, chroma_objects, source_id=source.id)
            log.info("automatic_chromadb_vectors_stored", tenant_id=tenant_str, upserted_count=upserted_count)
        except Exception as chroma_exc:
            log.warning("automatic_chromadb_store_warning", error=str(chroma_exc))
    except Exception as exc:
        log.warning("automatic_embeddings_json_failed", error=str(exc))
    
    # 4. Update Schema Registry (Deactivate previous, Activate newest)
    previous_entries = session.query(SchemaRegistry).filter_by(source_id=source.id, is_active=True).all()
    for prev in previous_entries:
        prev.is_active = False
    
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
    
    # 5. Record Ingestion Job
    job = IngestionJob(
        source_id=source.id,
        stage="Schema Extraction",
        status="succeeded",
        started_at=start_time,
        finished_at=finish_time,
        stats={
            "schema_version": next_version,
            "file_path": str(filepath),
            "sql_sha256": sql_sha256,
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
        # txt_path=str(txt_summary_filepath),
        tables=len(tables)
    )
    
    return {
        "status": "succeeded",
        "schema_id": str(new_registry.id),
        "version": next_version,
        "file_path": str(filepath),
        "sql_sha256": sql_sha256,
        "table_count": len(tables)
    }
