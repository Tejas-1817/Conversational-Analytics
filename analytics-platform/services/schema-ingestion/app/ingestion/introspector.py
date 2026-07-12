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

from app.models import ColumnMeta, DataSource, Relationship, TableMeta

log = structlog.get_logger()

_SYSTEM_SCHEMAS = {"information_schema", "pg_catalog", "pg_toast", "mysql", "performance_schema", "sys"}


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
            if f"{schema}.{table_name}" in blocklist or table_name in blocklist:
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

            _upsert_columns(session, inspector, table, schema, table_name, stats)

    # Deactivate tables that disappeared (diff-aware, non-destructive)
    for key, table in existing_tables.items():
        if key not in seen and table.is_active:
            table.is_active = False
            stats["tables_deactivated"] += 1
            log.info("table_deactivated", schema=key[0], table=key[1])

    session.flush()
    _record_declared_fks(session, inspector, source, stats)
    session.flush()
    return stats


def _upsert_columns(session: Session, inspector, table: TableMeta,
                    schema: str, table_name: str, stats: dict) -> None:
    pk_cols = set((inspector.get_pk_constraint(table_name, schema=schema) or {}).get("constrained_columns") or [])
    existing = {c.column_name: c for c in session.query(ColumnMeta).filter_by(table_id=table.id)}
    seen: set[str] = set()

    for position, col in enumerate(inspector.get_columns(table_name, schema=schema), start=1):
        name = col["name"]
        seen.add(name)
        stats["columns_seen"] += 1
        column = existing.get(name)
        if column is None:
            column = ColumnMeta(table_id=table.id, column_name=name, data_type=str(col["type"]))
            session.add(column)
        # Technical facts: always refreshed
        column.data_type = str(col["type"])
        column.is_nullable = bool(col.get("nullable", True))
        column.is_primary_key = name in pk_cols
        column.ordinal_position = position
        column.is_active = True
        db_comment = col.get("comment")
        if db_comment and not column.description:
            column.description = db_comment

    for name, column in existing.items():
        if name not in seen:
            column.is_active = False


def _record_declared_fks(session: Session, inspector, source: DataSource, stats: dict) -> None:
    """Declared foreign keys are database facts -> stored as approved with confidence 1.0."""
    columns_by_key = {
        (t.schema_name, t.table_name, c.column_name): c
        for t in session.query(TableMeta).filter_by(source_id=source.id, is_active=True)
        for c in t.columns
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
                exists = session.query(Relationship).filter_by(
                    from_column_id=from_col.id, to_column_id=to_col.id).one_or_none()
                if exists is None:
                    session.add(Relationship(
                        from_column_id=from_col.id, to_column_id=to_col.id,
                        cardinality="many_to_one", source="declared_fk", confidence=1.0,
                        evidence={"constraint_name": fk.get("name")}, status="approved",
                    ))
                    stats["declared_fks"] += 1
