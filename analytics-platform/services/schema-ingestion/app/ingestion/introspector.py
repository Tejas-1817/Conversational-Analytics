"""Stage 1 — Schema introspection.

Walks the customer database catalog via SQLAlchemy's Inspector (no hand-written
catalog SQL) and upserts tables/columns/declared FKs into the metadata repository.

Diff-aware re-runs:
- Technical facts (data types, keys, nullability) are always refreshed.
- Enriched fields (business_name, description, grain, synonyms, role...) are NEVER touched here.
- Objects that disappear are flagged is_active=false, never deleted.
"""
import structlog
from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.models import ColumnMeta, DataSource, Relationship, TableMeta, IndexMeta

log = structlog.get_logger()

_SYSTEM_SCHEMAS = {"information_schema", "pg_catalog", "pg_toast", "mysql", "performance_schema", "sys"}
_SYSTEM_TABLES = {
    "users", "tenants", "conversations", "conversation_messages", "data_sources",
    "ingestion_jobs", "dashboards", "saved_insights", "audit_log", "tenant_policies",
    "api_keys", "revoked_tokens", "oidc_providers", "tables_meta", "columns_meta",
    "index_meta", "relationships", "metadata_versions", "semantic_synonyms",
    "column_security_policies", "rls_policies", "user_feedback", "approved_sql_examples",
    "dashboard_widgets", "benchmark_collections", "evaluation_datasets", "evaluation_runs",
    "semantic_models", "semantic_dimensions", "semantic_joins", "semantic_feedback",
    "semantic_metrics", "business_glossary", "evaluation_results", "business_ontology",
    "ai_context", "metric_allowed_dimensions", "metric_allowed_filters", "glossary_links",
    "metric_versions", "dimension_versions", "join_versions", "semantic_kpis",
    "dashboard_recommendations", "suggested_questions", "chart_recommendations",
    "draft_semantic_columns", "draft_semantic_relationships", "draft_semantic_dimensions",
    "draft_semantic_tables", "draft_semantic_metrics", "draft_semantic_time_dimensions",
    "draft_semantic_join_paths", "draft_semantic_versions", "draft_semantic_audit_logs"
}


def run_introspection(session: Session, source: DataSource, engine: Engine) -> dict:
    inspector = inspect(engine)
    include = set(source.options.get("include_schemas") or [])
    blocklist = set(source.options.get("table_blocklist") or [])

    schemas = [s for s in inspector.get_schema_names() if s not in _SYSTEM_SCHEMAS]
    if include:
        schemas = [s for s in schemas if s in include]

    existing_tables = {(t.schema_name, t.table_name): t
                       for t in session.query(TableMeta).filter_by(source_id=source.id)}
    seen: set[tuple[str, str]] = set()
    stats = {"schemas": len(schemas), "tables_seen": 0, "tables_new": 0,
             "columns_seen": 0, "declared_fks": 0, "tables_deactivated": 0}

    for schema in schemas:
        for table_name in inspector.get_table_names(schema=schema):
            if table_name.lower() in _SYSTEM_TABLES or f"{schema}.{table_name}" in blocklist or table_name in blocklist:
                continue
            seen.add((schema, table_name))
            stats["tables_seen"] += 1

            table = existing_tables.get((schema, table_name))
            if table is None:
                table = TableMeta(source_id=source.id, schema_name=schema, table_name=table_name)
                session.add(table)
                session.flush()
                stats["tables_new"] += 1
            table.is_active = True

            comment = (inspector.get_table_comment(table_name, schema=schema) or {}).get("text")
            if comment and not table.description:
                table.description = comment  # DB comments seed drafts; approved text is never overwritten
                table.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

            changed = _upsert_columns(session, inspector, table, schema, table_name, stats)
            if changed:
                table.updated_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)

    # Deactivate tables that disappeared (diff-aware, non-destructive)
    for key, table in existing_tables.items():
        if key not in seen and table.is_active:
            table.is_active = False
            stats["tables_deactivated"] += 1
            log.info("table_deactivated", schema=key[0], table=key[1])

        if table.is_active:
            _upsert_indexes(session, inspector, table, key[0], key[1], stats)

    session.flush()
    _record_declared_fks(session, inspector, source, stats)
    session.flush()
    return stats


def _upsert_columns(session: Session, inspector, table: TableMeta,
                    schema: str, table_name: str, stats: dict) -> bool:
    pk_cols = set((inspector.get_pk_constraint(table_name, schema=schema) or {}).get("constrained_columns") or [])
    existing = {c.column_name: c for c in session.query(ColumnMeta).filter_by(table_id=table.id)}
    seen: set[str] = set()
    changed = False

    for position, col in enumerate(inspector.get_columns(table_name, schema=schema), start=1):
        name = col["name"]
        seen.add(name)
        stats["columns_seen"] += 1
        column = existing.get(name)
        
        is_new = False
        if column is None:
            column = ColumnMeta(table_id=table.id, column_name=name, data_type=str(col["type"]))
            session.add(column)
            is_new = True
            changed = True
            
        new_type = str(col["type"])
        new_nullable = bool(col.get("nullable", True))
        new_pk = name in pk_cols
        
        if not is_new:
            if (column.data_type != new_type or 
                column.is_nullable != new_nullable or 
                column.is_primary_key != new_pk or
                column.ordinal_position != position):
                changed = True
                
        # Technical facts: always refreshed
        column.data_type = new_type
        column.is_nullable = new_nullable
        column.is_primary_key = new_pk
        column.ordinal_position = position
        
        if not column.is_active:
            column.is_active = True
            changed = True
            
        db_comment = col.get("comment")
        if db_comment and not column.description:
            column.description = db_comment
            changed = True

    for name, column in existing.items():
        if name not in seen:
            if column.is_active:
                column.is_active = False
                changed = True
                
    return changed

def _upsert_indexes(session: Session, inspector, table: TableMeta, schema: str, table_name: str, stats: dict) -> None:
    existing = {idx.index_name: idx for idx in session.query(IndexMeta).filter_by(table_id=table.id)}
    seen = set()
    
    for idx in inspector.get_indexes(table_name, schema=schema):
        name = idx["name"]
        seen.add(name)
        
        index = existing.get(name)
        if index is None:
            index = IndexMeta(
                table_id=table.id,
                index_name=name,
                column_names=idx["column_names"],
                is_unique=idx["unique"]
            )
            session.add(index)
        else:
            index.column_names = idx["column_names"]
            index.is_unique = idx["unique"]
            
    for name, index in existing.items():
        if name not in seen:
            session.delete(index)

def _record_declared_fks(session: Session, inspector, source: DataSource, stats: dict) -> None:
    """Declared foreign keys are database facts -> stored as approved with confidence 1.0."""
    columns_by_key = {
        (t.schema_name, t.table_name, c.column_name): c
        for t in session.query(TableMeta).filter_by(source_id=source.id, is_active=True)
        for c in t.columns
    }
    
    existing_rels = {
        (r.from_column_id, r.to_column_id)
        for r in session.query(Relationship.from_column_id, Relationship.to_column_id)
        .join(ColumnMeta, Relationship.from_column_id == ColumnMeta.id)
        .join(TableMeta, ColumnMeta.table_id == TableMeta.id)
        .filter(TableMeta.source_id == source.id).all()
    }
    
    for table in session.query(TableMeta).filter_by(source_id=source.id, is_active=True):
        for fk in inspector.get_foreign_keys(table.table_name, schema=table.schema_name):
            ref_schema = fk.get("referred_schema") or table.schema_name
            for from_col_name, to_col_name in zip(fk["constrained_columns"], fk["referred_columns"], strict=True):
                from_col = columns_by_key.get((table.schema_name, table.table_name, from_col_name))
                to_col = columns_by_key.get((ref_schema, fk["referred_table"], to_col_name))
                if from_col is None or to_col is None:
                    log.warning("fk_endpoint_missing", table=table.table_name, fk=fk.get("name"))
                    continue
                    
                if (from_col.id, to_col.id) not in existing_rels:
                    session.add(Relationship(
                        from_column_id=from_col.id, to_column_id=to_col.id,
                        cardinality="many_to_one", source="declared_fk", confidence=1.0,
                        evidence={"constraint_name": fk.get("name")}, status="approved",
                    ))
                    stats["declared_fks"] += 1
