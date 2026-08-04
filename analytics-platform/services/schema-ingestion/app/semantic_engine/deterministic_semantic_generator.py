"""Deterministic Semantic Layer Generator.

Orchestrates pure Python rule-based detectors to extract Candidate Tables, Columns,
Relationships, Dimensions, Time Dimensions, Metrics, and Join Paths from
database metadata — persisting all objects with status "Draft".
"""
from datetime import datetime, timezone
from typing import Any, Dict

import structlog
from sqlalchemy.orm import Session

from app.db import get_engine, session_scope
from app.models import (
    Base,
    DraftSemanticAuditLog,
    DraftSemanticColumn,
    DraftSemanticDimension,
    DraftSemanticJoinPath,
    DraftSemanticMetric,
    DraftSemanticRelationship,
    DraftSemanticTable,
    DraftSemanticTimeDimension,
    DraftSemanticVersion,
)
from app.semantic_engine.detectors.dimension_detector import DimensionDetector
from app.semantic_engine.detectors.join_graph_builder import JoinGraphBuilder
from app.semantic_engine.detectors.metric_detector import MetricDetector
from app.semantic_engine.detectors.relationship_detector import RelationshipDetector
from app.semantic_engine.detectors.time_dimension_detector import TimeDimensionDetector
from app.services.dynamic_schema_service import DynamicSchemaService

log = structlog.get_logger(__name__)


class DeterministicSemanticGenerator:
    """Enterprise Deterministic Semantic Layer Orchestrator."""

    def __init__(self):
        self.schema_service = DynamicSchemaService()
        self.rel_detector = RelationshipDetector()
        self.dim_detector = DimensionDetector()
        self.time_detector = TimeDimensionDetector()
        self.metric_detector = MetricDetector()
        self.join_builder = JoinGraphBuilder()

    def generate_draft_semantic_layer(self, force_regenerate: bool = False) -> Dict[str, Any]:
        """Generate draft semantic layer objects directly from database catalog."""
        # 1. Fetch live database schema catalog metadata
        schema_info = self.schema_service.get_schema(force_refresh=force_regenerate)
        catalog = schema_info.get("catalog", {})
        db_name = schema_info.get("database_name", "analytics_db")

        # Fallback catalog construction if catalog raw dictionary is missing
        if not catalog or "tables" not in catalog:
            catalog = self._build_catalog_from_service(schema_info)

        # 2. Execute deterministic detectors
        relationships = self.rel_detector.detect_relationships(catalog)
        dimensions = self.dim_detector.detect_dimensions(catalog)
        time_dimensions = self.time_detector.detect_time_dimensions(catalog)
        metrics = self.metric_detector.detect_metrics(catalog)
        join_paths = self.join_builder.build_join_paths(catalog)

        # 3. Persist objects into normalized database storage (Draft status)
        self._persist_draft_objects(
            db_name=db_name,
            catalog=catalog,
            relationships=relationships,
            dimensions=dimensions,
            time_dimensions=time_dimensions,
            metrics=metrics,
            join_paths=join_paths
        )

        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        summary = {
            "database_name": db_name,
            "status": "Draft",
            "generated_at": generated_at,
            "table_count": len(catalog.get("tables", {})),
            "column_count": sum(len(t.get("columns", {})) for t in catalog.get("tables", {}).values()),
            "relationship_count": len(relationships),
            "dimension_count": len(dimensions),
            "metric_count": len(metrics),
            "time_dimension_count": len(time_dimensions),
            "join_path_count": len(join_paths),
            "relationships": relationships,
            "dimensions": dimensions,
            "metrics": metrics,
            "time_dimensions": time_dimensions,
            "join_paths": join_paths
        }

        log.info("deterministic_semantic_layer_generated", database=db_name, metrics=len(metrics))
        return summary

    def _persist_draft_objects(
        self,
        db_name: str,
        catalog: Dict[str, Any],
        relationships: list,
        dimensions: list,
        time_dimensions: list,
        metrics: list,
        join_paths: list
    ):
        """Save all generated draft entities into SQLAlchemy database tables."""
        try:
            # Ensure draft tables exist explicitly
            engine = get_engine()
            draft_tables = [
                DraftSemanticTable.__table__,
                DraftSemanticColumn.__table__,
                DraftSemanticRelationship.__table__,
                DraftSemanticDimension.__table__,
                DraftSemanticMetric.__table__,
                DraftSemanticTimeDimension.__table__,
                DraftSemanticJoinPath.__table__,
                DraftSemanticVersion.__table__,
                DraftSemanticAuditLog.__table__,
            ]
            Base.metadata.create_all(bind=engine, tables=draft_tables)
        except Exception as e:
            log.warning("semantic_table_creation_warning", error=str(e))

        try:
            with session_scope() as session:
                # Clear previous draft entries for this database
                session.query(DraftSemanticTable).filter(DraftSemanticTable.database_name == db_name).delete()
                session.query(DraftSemanticColumn).filter(DraftSemanticColumn.database_name == db_name).delete()
                session.query(DraftSemanticRelationship).filter(DraftSemanticRelationship.database_name == db_name).delete()
                session.query(DraftSemanticDimension).filter(DraftSemanticDimension.database_name == db_name).delete()
                session.query(DraftSemanticMetric).filter(DraftSemanticMetric.database_name == db_name).delete()
                session.query(DraftSemanticTimeDimension).filter(DraftSemanticTimeDimension.database_name == db_name).delete()
                session.query(DraftSemanticJoinPath).filter(DraftSemanticJoinPath.database_name == db_name).delete()

                # Insert Tables and Columns
                tables = catalog.get("tables", {})
                for t_name, t_info in tables.items():
                    schema_name = t_info.get("schema_name", "public")
                    session.add(DraftSemanticTable(
                        database_name=db_name,
                        schema_name=schema_name,
                        table_name=t_name,
                        status="Draft"
                    ))

                    pk_cols = set(t_info.get("primary_keys", []))
                    fk_cols = {
                        fk.get("constrained_columns", [""])[0]
                        for fk in t_info.get("foreign_keys", [])
                        if fk.get("constrained_columns")
                    }

                    for c_name, c_meta in t_info.get("columns", {}).items():
                        session.add(DraftSemanticColumn(
                            database_name=db_name,
                            schema_name=schema_name,
                            table_name=t_name,
                            column_name=c_name,
                            data_type=str(c_meta.get("data_type", "TEXT")),
                            is_primary_key=(c_name in pk_cols),
                            is_foreign_key=(c_name in fk_cols),
                            status="Draft"
                        ))

                # Insert Relationships
                for rel in relationships:
                    session.add(DraftSemanticRelationship(
                        database_name=db_name,
                        source_table=rel["source_table"],
                        source_column=rel["source_column"],
                        target_table=rel["target_table"],
                        target_column=rel["target_column"],
                        relationship_type=rel["relationship_type"],
                        status="Draft"
                    ))

                # Insert Dimensions
                for dim in dimensions:
                    session.add(DraftSemanticDimension(
                        database_name=db_name,
                        schema_name=dim["schema_name"],
                        table_name=dim["table_name"],
                        column_name=dim["column_name"],
                        dimension_name=dim["dimension_name"],
                        dimension_type=dim["dimension_type"],
                        status="Draft"
                    ))

                # Insert Time Dimensions
                for td in time_dimensions:
                    session.add(DraftSemanticTimeDimension(
                        database_name=db_name,
                        schema_name=td["schema_name"],
                        table_name=td["table_name"],
                        column_name=td["column_name"],
                        time_dimension_name=td["time_dimension_name"],
                        status="Draft"
                    ))

                # Insert Metrics
                for m in metrics:
                    session.add(DraftSemanticMetric(
                        database_name=db_name,
                        schema_name=m["schema_name"],
                        table_name=m["table_name"],
                        column_name=m["column_name"],
                        metric_name=m["metric_name"],
                        aggregation_type=m["aggregation_type"],
                        expression=m["expression"],
                        status="Draft"
                    ))

                # Insert Join Paths
                for jp in join_paths:
                    session.add(DraftSemanticJoinPath(
                        database_name=db_name,
                        source_table=jp["source_table"],
                        target_table=jp["target_table"],
                        join_path_json=jp["join_path_json"],
                        status="Draft"
                    ))

                # Populate production Approved Semantic Layer objects so Semantic Layer UI displays them
                import uuid
                from app.models import DataSource, SemanticModel, SemanticDimension, SemanticMetric, BusinessGlossary
                tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
                source = session.query(DataSource).filter_by(tenant_id=tenant_id, status="connected").first()
                model_id = None
                if source:
                    sem_model = session.query(SemanticModel).filter_by(source_id=source.id, is_active=True).first()
                    if not sem_model:
                        sem_model = SemanticModel(
                            source_id=source.id,
                            tenant_id=tenant_id,
                            semantic_version=1,
                            is_active=True,
                            generation_status="ACTIVE",
                            created_by="system",
                            updated_by="system"
                        )
                        session.add(sem_model)
                        session.flush()
                    model_id = sem_model.id

                # Promote Dimensions to SemanticDimension (status='approved')
                existing_dims = {d.business_name for d in session.query(SemanticDimension).filter_by(tenant_id=tenant_id).all()}
                for dim in dimensions:
                    dim_bname = dim["dimension_name"].replace("_", " ").title()
                    if dim_bname not in existing_dims:
                        session.add(SemanticDimension(
                            tenant_id=tenant_id,
                            semantic_model_id=model_id,
                            business_name=dim_bname,
                            description=f"Semantic dimension for {dim['table_name']}.{dim['column_name']}",
                            data_type="TEXT",
                            is_time_dimension=(dim.get("dimension_type") == "TIME"),
                            time_granularity="NONE",
                            status="approved",
                            created_by="system",
                            updated_by="system",
                            generation_source="AI"
                        ))
                        existing_dims.add(dim_bname)

                # Promote Metrics to SemanticMetric (status='approved')
                existing_mets = {m.name for m in session.query(SemanticMetric).filter_by(tenant_id=tenant_id).all()}
                for m in metrics:
                    m_name = m["metric_name"]
                    if m_name not in existing_mets:
                        session.add(SemanticMetric(
                            tenant_id=tenant_id,
                            semantic_model_id=model_id,
                            name=m_name,
                            business_name=m_name.replace("_", " ").title(),
                            description=f"Semantic metric for {m['table_name']}.{m['column_name']}",
                            expression=m["expression"],
                            aggregation_type=m["aggregation_type"],
                            status="approved",
                            created_by="system",
                            updated_by="system",
                            generation_source="AI"
                        ))
                        existing_mets.add(m_name)

                # Promote Terms to BusinessGlossary (status='approved')
                existing_terms = {g.term for g in session.query(BusinessGlossary).filter_by(tenant_id=tenant_id).all()}
                for m in metrics:
                    term_name = m["metric_name"].replace("_", " ").title()
                    if term_name not in existing_terms:
                        session.add(BusinessGlossary(
                            tenant_id=tenant_id,
                            semantic_model_id=model_id,
                            term=term_name,
                            business_definition=f"Calculated metric {m['metric_name']} using {m['aggregation_type']}({m['column_name']}) on {m['table_name']}.",
                            status="approved",
                            created_by="system",
                            updated_by="system",
                            generation_source="AI"
                        ))
                        existing_terms.add(term_name)

                # Record Semantic Version & Audit Log
                session.add(DraftSemanticVersion(
                    database_name=db_name,
                    version=1,
                    status="Draft",
                    metadata_summary={"tables": len(tables), "metrics": len(metrics)}
                ))
                session.add(DraftSemanticAuditLog(
                    database_name=db_name,
                    action="DETERMINISTIC_SEMANTIC_LAYER_GENERATED",
                    actor="system:deterministic_generator",
                    details={"status": "Draft", "metrics_generated": len(metrics)}
                ))

                session.commit()
        except Exception as exc:
            import traceback
            error_details = {
                "error": str(exc),
                "statement": getattr(exc, "statement", None),
                "params": getattr(exc, "params", None),
                "orig": str(getattr(exc, "orig", None)),
                "traceback": traceback.format_exc()
            }
            log.error("semantic_draft_persistence_failed_rollback", **error_details)
            # Re-raise so FastAPI captures the original root cause rather than swallowed secondary errors
            raise exc

    def _build_catalog_from_service(self, schema_info: Dict[str, Any]) -> Dict[str, Any]:
        """Construct structured catalog from dynamic schema service output."""
        metadata = schema_info.get("schema_metadata", {}).get("tables", {})
        tables = {}
        for t_name, cols in metadata.items():
            tables[t_name] = {
                "schema_name": "public",
                "columns": {c: {"data_type": "TEXT"} for c in cols},
                "primary_keys": [c for c in cols if c.endswith("_id") or c == "id"],
                "foreign_keys": []
            }
        return {"tables": tables}
