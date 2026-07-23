import json
import uuid
from typing import Dict, Any
from sqlalchemy.orm import Session, selectinload

from app.models import TableMeta, ColumnMeta, Relationship, IndexMeta

class BusinessContextBuilder:
    """
    Builds a structured dictionary of metadata to feed the LLM prompts.
    It retrieves table details, column profiles, relationships, and indexes
    without making any LLM calls.
    """
    
    @staticmethod
    def build_table_context(db: Session, table_id: uuid.UUID) -> str:
        table = db.query(TableMeta).options(selectinload(TableMeta.columns)).filter(TableMeta.id == table_id).first()
        if not table:
            raise ValueError(f"Table {table_id} not found.")

        # Gather columns
        columns = table.columns or db.query(ColumnMeta).filter(ColumnMeta.table_id == table_id).all()
        
        column_context = []
        col_id_to_name = {}
        for col in columns:
            col_id_to_name[col.id] = col.column_name
            column_context.append({
                "name": col.column_name,
                "data_type": col.data_type,
                "is_nullable": col.is_nullable,
                "is_primary_key": col.is_primary_key,
                "role": col.role,
                "profile_stats": col.profile  # e.g., distinct_count, min, max, top_values
            })

        # Gather indexes
        indexes = db.query(IndexMeta).filter(IndexMeta.table_id == table_id).all()
        index_context = [{"name": idx.index_name, "columns": idx.column_names, "is_unique": idx.is_unique} for idx in indexes]

        # Gather relationships (Outbound and Inbound)
        if col_id_to_name:
            outbound_rels = db.query(Relationship).filter(Relationship.from_column_id.in_(col_id_to_name.keys())).all()
            inbound_rels = db.query(Relationship).filter(Relationship.to_column_id.in_(col_id_to_name.keys())).all()
        else:
            outbound_rels = []
            inbound_rels = []

        # Bulk resolve all foreign column IDs at once to prevent N+1 queries
        foreign_col_ids = set()
        for rel in outbound_rels:
            if rel.to_column_id not in col_id_to_name:
                foreign_col_ids.add(rel.to_column_id)
        for rel in inbound_rels:
            if rel.from_column_id not in col_id_to_name:
                foreign_col_ids.add(rel.from_column_id)

        foreign_name_map = {}
        if foreign_col_ids:
            foreign_cols = db.query(ColumnMeta).options(selectinload(ColumnMeta.table)).filter(ColumnMeta.id.in_(foreign_col_ids)).all()
            for fc in foreign_cols:
                tbl_name = fc.table.table_name if fc.table else ""
                foreign_name_map[fc.id] = f"{tbl_name}.{fc.column_name}" if tbl_name else fc.column_name

        def _resolve_col_name(col_id):
            if col_id in col_id_to_name:
                return col_id_to_name[col_id]
            return foreign_name_map.get(col_id, str(col_id))

        rel_context = []
        for rel in outbound_rels:
            rel_context.append({
                "direction": "outbound",
                "local_column": _resolve_col_name(rel.from_column_id),
                "foreign_column": _resolve_col_name(rel.to_column_id),
                "cardinality": rel.cardinality
            })
            
        for rel in inbound_rels:
            rel_context.append({
                "direction": "inbound",
                "foreign_column": _resolve_col_name(rel.from_column_id),
                "local_column": _resolve_col_name(rel.to_column_id),
                "cardinality": rel.cardinality
            })

        context = {
            "table": {
                "schema": table.schema_name,
                "name": table.table_name,
                "row_count": table.row_count
            },
            "columns": column_context,
            "indexes": index_context,
            "relationships": rel_context
        }
        
        return json.dumps(context, separators=(',', ':'))

    @staticmethod
    def build_global_context(db: Session, source_id: uuid.UUID) -> str:
        """
        Builds a lightweight global context covering all tables in the data source.
        Only includes table names, descriptions (enriched from Stage 1), and key relationships
        to prevent exceeding the LLM token limit.
        """
        tables = db.query(TableMeta).options(selectinload(TableMeta.columns)).filter(TableMeta.source_id == source_id, TableMeta.is_active == True).all()
        
        table_context = []
        for t in tables:
            cols = []
            for c in (t.columns or []):
                if c.is_primary_key or "FOREIGN" in (c.role or ""):
                    cols.append({"name": c.column_name, "role": c.role})
                    
            table_context.append({
                "name": t.table_name,
                "description": t.description,
                "key_columns": cols,
                "row_count": t.row_count
            })
            
        context = {
            "database_overview": table_context
        }
        return json.dumps(context, separators=(',', ':'))

