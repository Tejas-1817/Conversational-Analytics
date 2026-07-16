import uuid
import structlog
from sqlalchemy.orm import Session
from sqlalchemy import text, bindparam
from app.models import SemanticModel

logger = structlog.get_logger(__name__)

class SemanticVersionManager:
    """
    Manages the lifecycle, cloning, and atomic promotion of SemanticModel versions.
    """

    @staticmethod
    def initialize_version(db: Session, source_id: uuid.UUID, tenant_id: uuid.UUID, metadata_version_id: uuid.UUID) -> SemanticModel:
        max_semantic = db.query(SemanticModel).filter_by(source_id=source_id).order_by(SemanticModel.semantic_version.desc()).first()
        new_version = (max_semantic.semantic_version + 1) if max_semantic else 1
        
        semantic_model = SemanticModel(
            tenant_id=tenant_id,
            source_id=source_id,
            metadata_version_id=metadata_version_id,
            semantic_version=new_version,
            generated_by_model="huggingface_orchestrator",
            generation_status="GENERATING",
            is_active=False
        )
        db.add(semantic_model)
        db.flush()
        return semantic_model

    @staticmethod
    def clone_unchanged_entities(db: Session, old_model_id: uuid.UUID, new_model_id: uuid.UUID, changed_table_ids: list[uuid.UUID]):
        """
        Executes bulk INSERT INTO ... SELECT statements to clone unchanged semantic entities
        from the old version to the new version.
        MANUAL entities are always cloned.
        AI entities are cloned only if their underlying table has not changed.
        """
        logger.info("cloning_unchanged_semantic_entities", old_model_id=str(old_model_id), new_model_id=str(new_model_id))
        
        if not changed_table_ids:
            # Fallback safe values if somehow called with empty list
            changed_tuple = tuple([str(uuid.uuid4())])
        else:
            changed_tuple = tuple(str(x) for x in changed_table_ids)
            
        params = {
            "new_model_id": str(new_model_id),
            "old_model_id": str(old_model_id),
            "changed_table_ids": changed_tuple
        }

        # 1. Semantic Dimensions
        db.execute(text("""
            INSERT INTO semantic_dimensions (
                tenant_id, business_name, description, semantic_model_id, source_table_id,
                source_column_id, data_type, is_time_dimension, time_granularity,
                visibility, status, version, created_by, updated_by,
                generation_source, confidence_score, prompt_version, review_status
            )
            SELECT 
                tenant_id, business_name, description, :new_model_id, source_table_id,
                source_column_id, data_type, is_time_dimension, time_granularity,
                visibility, status, version, created_by, updated_by,
                generation_source, confidence_score, prompt_version, review_status
            FROM semantic_dimensions
            WHERE semantic_model_id = :old_model_id
              AND (generation_source = 'MANUAL' OR source_table_id NOT IN :changed_table_ids)
        """).bindparams(bindparam("changed_table_ids", expanding=True)), params)

        # 2. Semantic Metrics
        db.execute(text("""
            INSERT INTO semantic_metrics (
                tenant_id, name, business_name, description, semantic_model_id, is_calculated,
                aggregation_type, expression, source_table_id, source_column_id,
                owner, status, version, created_by, updated_by,
                generation_source, confidence_score, prompt_version, review_status
            )
            SELECT 
                tenant_id, name, business_name, description, :new_model_id, is_calculated,
                aggregation_type, expression, source_table_id, source_column_id,
                owner, status, version, created_by, updated_by,
                generation_source, confidence_score, prompt_version, review_status
            FROM semantic_metrics
            WHERE semantic_model_id = :old_model_id
              AND (generation_source = 'MANUAL' OR source_table_id NOT IN :changed_table_ids)
        """).bindparams(bindparam("changed_table_ids", expanding=True)), params)

        # 3. Semantic Joins
        db.execute(text("""
            INSERT INTO semantic_joins (
                tenant_id, semantic_model_id, left_table_id, left_column_id, right_table_id, right_column_id,
                join_condition, join_type, cardinality, confidence, status, version,
                created_by, updated_by, generation_source, prompt_version, review_status
            )
            SELECT 
                tenant_id, :new_model_id, left_table_id, left_column_id, right_table_id, right_column_id,
                join_condition, join_type, cardinality, confidence, status, version,
                created_by, updated_by, generation_source, prompt_version, review_status
            FROM semantic_joins
            WHERE semantic_model_id = :old_model_id
              AND (generation_source = 'MANUAL' OR (left_table_id NOT IN :changed_table_ids AND right_table_id NOT IN :changed_table_ids))
        """).bindparams(bindparam("changed_table_ids", expanding=True)), params)

        # 4. Global Entities (Clone ONLY MANUAL ones, AI will regenerate)
        db.execute(text("""
            INSERT INTO business_glossary (
                tenant_id, semantic_model_id, term, business_definition, owner, status,
                created_by, updated_by, generation_source, confidence_score, prompt_version, review_status
            )
            SELECT 
                tenant_id, :new_model_id, term, business_definition, owner, status,
                created_by, updated_by, generation_source, confidence_score, prompt_version, review_status
            FROM business_glossary
            WHERE semantic_model_id = :old_model_id AND generation_source = 'MANUAL'
        """), params)

        db.execute(text("""
            INSERT INTO business_ontology (
                semantic_model_id, domain, description, confidence, status, reviewed, approved, source,
                generation_source, confidence_score, prompt_version, review_status
            )
            SELECT 
                :new_model_id, domain, description, confidence, status, reviewed, approved, source,
                generation_source, confidence_score, prompt_version, review_status
            FROM business_ontology
            WHERE semantic_model_id = :old_model_id AND generation_source = 'MANUAL'
        """), params)

        db.execute(text("""
            INSERT INTO semantic_kpis (
                semantic_model_id, ontology_id, name, description, formula, dimensions, measures,
                confidence, status, reviewed, approved, source,
                generation_source, confidence_score, prompt_version, review_status
            )
            SELECT 
                :new_model_id, bo_new.id, k.name, k.description, k.formula, k.dimensions, k.measures,
                k.confidence, k.status, k.reviewed, k.approved, k.source,
                k.generation_source, k.confidence_score, k.prompt_version, k.review_status
            FROM semantic_kpis k
            LEFT JOIN business_ontology bo_old ON k.ontology_id = bo_old.id
            LEFT JOIN business_ontology bo_new ON bo_old.domain = bo_new.domain AND bo_new.semantic_model_id = :new_model_id
            WHERE k.semantic_model_id = :old_model_id AND k.generation_source = 'MANUAL'
        """), params)

        db.execute(text("""
            INSERT INTO dashboard_recommendations (
                semantic_model_id, ontology_id, name, description, business_goal, structure,
                confidence, status, reviewed, approved, source,
                generation_source, confidence_score, prompt_version, review_status
            )
            SELECT 
                :new_model_id, bo_new.id, d.name, d.description, d.business_goal, d.structure,
                d.confidence, d.status, d.reviewed, d.approved, d.source,
                d.generation_source, d.confidence_score, d.prompt_version, d.review_status
            FROM dashboard_recommendations d
            LEFT JOIN business_ontology bo_old ON d.ontology_id = bo_old.id
            LEFT JOIN business_ontology bo_new ON bo_old.domain = bo_new.domain AND bo_new.semantic_model_id = :new_model_id
            WHERE d.semantic_model_id = :old_model_id AND d.generation_source = 'MANUAL'
        """), params)

        db.execute(text("""
            INSERT INTO suggested_questions (
                semantic_model_id, ontology_id, entity_name, question, filter_logic,
                confidence, status, reviewed, approved, source,
                generation_source, confidence_score, prompt_version, review_status
            )
            SELECT 
                :new_model_id, bo_new.id, q.entity_name, q.question, q.filter_logic,
                q.confidence, q.status, q.reviewed, q.approved, q.source,
                q.generation_source, q.confidence_score, q.prompt_version, q.review_status
            FROM suggested_questions q
            LEFT JOIN business_ontology bo_old ON q.ontology_id = bo_old.id
            LEFT JOIN business_ontology bo_new ON bo_old.domain = bo_new.domain AND bo_new.semantic_model_id = :new_model_id
            WHERE q.semantic_model_id = :old_model_id AND q.generation_source = 'MANUAL'
        """), params)

        db.execute(text("""
            INSERT INTO ai_context (
                semantic_model_id, purpose, default_filters, time_intelligence, chart_preferences, context_payload,
                confidence, status, reviewed, approved, source,
                generation_source, confidence_score, prompt_version, review_status
            )
            SELECT 
                :new_model_id, purpose, default_filters, time_intelligence, chart_preferences, context_payload,
                confidence, status, reviewed, approved, source,
                generation_source, confidence_score, prompt_version, review_status
            FROM ai_context
            WHERE semantic_model_id = :old_model_id AND generation_source = 'MANUAL'
        """), params)
        
        db.execute(text("""
            INSERT INTO chart_recommendations (
                semantic_model_id, dashboard_id, kpi_name, insight_type, chart_type, applicability,
                confidence, status, reviewed, approved, source,
                generation_source, confidence_score, prompt_version, review_status
            )
            SELECT 
                :new_model_id, dr_new.id, c.kpi_name, c.insight_type, c.chart_type, c.applicability,
                c.confidence, c.status, c.reviewed, c.approved, c.source,
                c.generation_source, c.confidence_score, c.prompt_version, c.review_status
            FROM chart_recommendations c
            LEFT JOIN dashboard_recommendations dr_old ON c.dashboard_id = dr_old.id
            LEFT JOIN dashboard_recommendations dr_new ON dr_old.name = dr_new.name AND dr_new.semantic_model_id = :new_model_id
            WHERE c.semantic_model_id = :old_model_id AND c.generation_source = 'MANUAL'
        """), params)
        
        db.flush()

    @staticmethod
    def promote_version(db: Session, source_id: uuid.UUID, new_model_id: uuid.UUID):
        """
        Atomically demotes the old version and activates the new version.
        """
        logger.info("promoting_semantic_version", new_model_id=str(new_model_id))
        
        db.query(SemanticModel).filter(
            SemanticModel.source_id == source_id,
            SemanticModel.is_active == True
        ).update({"is_active": False})
        
        db.query(SemanticModel).filter(
            SemanticModel.id == new_model_id
        ).update({
            "is_active": True,
            "generation_status": "ACTIVE"
        })
        
        db.commit()
