import structlog
import uuid
from sqlalchemy.orm import Session

from app.models import (
    TableMeta, ColumnMeta, SemanticDimension, SemanticMetric,
    BusinessGlossary, SemanticJoin, SemanticModel,
    BusinessOntology, SemanticKPI, DashboardRecommendation,
    SuggestedQuestion, AIContext, ChartRecommendation
)
from app.llm.orchestrator import ai_orchestrator
from app.semantic.context_builder import BusinessContextBuilder
from app.llm.prompts.semantic_prompts import SemanticPromptBuilder
from app.schemas_semantic_ai import AITableEnrichmentSchema, AIGlobalEnrichmentSchema

logger = structlog.get_logger(__name__)

class SemanticEnrichmentService:
    """
    Orchestrates the AI semantic enrichment pipeline (both Table-Level and Global).
    """
    
    @classmethod
    def enrich_table(cls, db: Session, table_id: uuid.UUID, tenant_id: uuid.UUID, semantic_model_id: uuid.UUID | None = None):
        logger.info("starting_table_enrichment", table_id=str(table_id))
        
        table = db.query(TableMeta).filter(TableMeta.id == table_id).first()
        if not table:
            return
            
        context_json = BusinessContextBuilder.build_table_context(db, table_id)
        prompt = SemanticPromptBuilder.build_table_enrichment_prompt(context_json)
        
        try:
            enrichment: AITableEnrichmentSchema = ai_orchestrator.generate_structured(
                prompt=prompt,
                schema=AITableEnrichmentSchema
            )
        except Exception as e:
            logger.error("table_enrichment_failed", table_id=str(table_id), error=str(e))
            return
            
        cls._persist_table_enrichment(db, table, tenant_id, semantic_model_id, enrichment)
        logger.info("finished_table_enrichment", table_id=str(table_id))

    @classmethod
    def _persist_table_enrichment(cls, db: Session, table: TableMeta, tenant_id: uuid.UUID, semantic_model_id: uuid.UUID | None, enrichment: AITableEnrichmentSchema):
        columns = db.query(ColumnMeta).filter(ColumnMeta.table_id == table.id).all()
        col_map = {col.column_name.lower(): col for col in columns}
        tables = db.query(TableMeta).filter(TableMeta.source_id == table.source_id).all()
        table_map = {t.table_name.lower(): t for t in tables}
        
        review_status = "ACTIVE" if enrichment.confidence_score >= 0.8 else "REVIEW_REQUIRED"
        
        if enrichment.business_description and not table.description:
            table.description = enrichment.business_description
        
        # Dimensions
        for dim_schema in enrichment.dimensions:
            col = col_map.get(dim_schema.source_column_name.lower())
            if not col:
                continue
            
            exists = db.query(SemanticDimension).filter(
                SemanticDimension.source_column_id == col.id,
                SemanticDimension.semantic_model_id == semantic_model_id
            ).first()
            if not exists:
                db.add(SemanticDimension(
                    tenant_id=tenant_id,
                    semantic_model_id=semantic_model_id,
                    business_name=dim_schema.business_name,
                    description=dim_schema.description,
                    source_table_id=table.id,
                    source_column_id=col.id,
                    data_type=col.data_type,
                    is_time_dimension=dim_schema.is_time_dimension,
                    time_granularity=dim_schema.time_granularity,
                    created_by="ai_generator",
                    updated_by="ai_generator",
                    generation_source="AI",
                    confidence_score=enrichment.confidence_score,
                    prompt_version=SemanticPromptBuilder.PROMPT_VERSION,
                    review_status=review_status
                ))

        # Measures
        for measure_schema in enrichment.measures:
            col = col_map.get(measure_schema.source_column_name.lower())
            if not col:
                continue
                
            exists = db.query(SemanticMetric).filter(
                SemanticMetric.source_column_id == col.id,
                SemanticMetric.is_calculated == False,
                SemanticMetric.semantic_model_id == semantic_model_id
            ).first()
            if not exists:
                db.add(SemanticMetric(
                    tenant_id=tenant_id,
                    name=measure_schema.business_name,
                    description=measure_schema.description,
                    semantic_model_id=semantic_model_id,
                    is_calculated=False,
                    aggregation_type=measure_schema.aggregation_type.upper(),
                    expression=f"{{{{ {measure_schema.source_column_name} }}}}",
                    source_table_id=table.id,
                    source_column_id=col.id,
                    created_by="ai_generator",
                    updated_by="ai_generator",
                    generation_source="AI",
                    confidence_score=enrichment.confidence_score,
                    prompt_version=SemanticPromptBuilder.PROMPT_VERSION,
                    review_status=review_status
                ))
                
        # KPIs
        for kpi_schema in enrichment.kpis:
            exists = db.query(SemanticKPI).filter(
                SemanticKPI.name == kpi_schema.business_name,
                SemanticKPI.semantic_model_id == semantic_model_id
            ).first()
            if not exists:
                db.add(SemanticKPI(
                    semantic_model_id=semantic_model_id,
                    name=kpi_schema.business_name,
                    description=kpi_schema.description,
                    formula=kpi_schema.expression,
                    dimensions=[],
                    measures=[],
                    confidence=enrichment.confidence_score,
                    confidence_score=enrichment.confidence_score,
                    generation_source="AI",
                    prompt_version=SemanticPromptBuilder.PROMPT_VERSION,
                    review_status=review_status
                ))
                
        # Glossary
        for term_schema in enrichment.glossary_terms:
            exists = db.query(BusinessGlossary).filter(
                BusinessGlossary.term == term_schema.term,
                BusinessGlossary.semantic_model_id == semantic_model_id
            ).first()
            if not exists:
                db.add(BusinessGlossary(
                    tenant_id=tenant_id,
                    term=term_schema.term,
                    business_definition=term_schema.business_definition,
                    semantic_model_id=semantic_model_id,
                    created_by="ai_generator",
                    updated_by="ai_generator",
                    generation_source="AI",
                    confidence_score=enrichment.confidence_score,
                    prompt_version=SemanticPromptBuilder.PROMPT_VERSION,
                    review_status=review_status
                ))

        # Relationships
        for rel_schema in enrichment.relationships:
            local_col = col_map.get(rel_schema.from_column_name.lower())
            target_table = table_map.get(rel_schema.to_table_name.lower())
            if not local_col or not target_table:
                continue
                
            # fetch columns for target table
            target_cols = db.query(ColumnMeta).filter(ColumnMeta.table_id == target_table.id).all()
            target_col_map = {c.column_name.lower(): c for c in target_cols}
            target_col = target_col_map.get(rel_schema.to_column_name.lower())
            
            if not target_col:
                continue
                
            exists = db.query(SemanticJoin).filter(
                SemanticJoin.left_column_id == local_col.id,
                SemanticJoin.right_column_id == target_col.id,
                SemanticJoin.semantic_model_id == semantic_model_id
            ).first()
            
            if not exists:
                db.add(SemanticJoin(
                    tenant_id=tenant_id,
                    semantic_model_id=semantic_model_id,
                    left_table_id=table.id,
                    left_column_id=local_col.id,
                    right_table_id=target_table.id,
                    right_column_id=target_col.id,
                    join_type="LEFT",
                    join_condition=f"{{{{ {table.table_name}.{local_col.column_name} }}}} = {{{{ {target_table.table_name}.{target_col.column_name} }}}}",
                    relationship_type=rel_schema.cardinality,
                    created_by="ai_generator",
                    updated_by="ai_generator",
                    generation_source="AI",
                    confidence=enrichment.confidence_score,
                    prompt_version=SemanticPromptBuilder.PROMPT_VERSION,
                    review_status=review_status
                ))

        db.commit()

    @classmethod
    def enrich_global(cls, db: Session, source_id: uuid.UUID, semantic_model_id: uuid.UUID):
        logger.info("starting_global_enrichment", source_id=str(source_id))
        
        context_json = BusinessContextBuilder.build_global_context(db, source_id)
        prompt = SemanticPromptBuilder.build_global_enrichment_prompt(context_json)
        
        try:
            enrichment: AIGlobalEnrichmentSchema = ai_orchestrator.generate_structured(
                prompt=prompt,
                schema=AIGlobalEnrichmentSchema
            )
        except Exception as e:
            logger.error("global_enrichment_failed", source_id=str(source_id), error=str(e))
            return
            
        cls._persist_global_enrichment(db, semantic_model_id, enrichment)
        logger.info("finished_global_enrichment", source_id=str(source_id))

    @classmethod
    def _persist_global_enrichment(cls, db: Session, semantic_model_id: uuid.UUID, enrichment: AIGlobalEnrichmentSchema):
        review_status = "ACTIVE" if enrichment.confidence_score >= 0.8 else "REVIEW_REQUIRED"
        
        # Ontology
        for ont in enrichment.ontology:
            db.add(BusinessOntology(
                semantic_model_id=semantic_model_id,
                domain=ont.domain,
                description=ont.description,
                confidence=enrichment.confidence_score,
                confidence_score=enrichment.confidence_score,
                generation_source="AI",
                prompt_version=SemanticPromptBuilder.PROMPT_VERSION,
                review_status=review_status
            ))
            
        # Cross-Table KPIs
        for kpi in enrichment.kpis:
            db.add(SemanticKPI(
                semantic_model_id=semantic_model_id,
                name=kpi.name,
                description=kpi.description,
                formula=kpi.formula,
                dimensions=kpi.dimensions,
                measures=kpi.measures,
                confidence=enrichment.confidence_score,
                confidence_score=enrichment.confidence_score,
                generation_source="AI",
                prompt_version=SemanticPromptBuilder.PROMPT_VERSION,
                review_status=review_status
            ))
            
        # Dashboards
        dashboard_objs = []
        for dash in enrichment.dashboards:
            d_obj = DashboardRecommendation(
                semantic_model_id=semantic_model_id,
                name=dash.name,
                description=dash.description,
                business_goal=dash.business_goal,
                structure={"widgets": [w.model_dump() for w in dash.widgets]},
                confidence=enrichment.confidence_score,
                confidence_score=enrichment.confidence_score,
                generation_source="AI",
                prompt_version=SemanticPromptBuilder.PROMPT_VERSION,
                review_status=review_status
            )
            db.add(d_obj)
            dashboard_objs.append((dash, d_obj))
            
        db.flush()
        
        for dash_schema, d_obj in dashboard_objs:
            for widget in dash_schema.widgets:
                db.add(ChartRecommendation(
                    semantic_model_id=semantic_model_id,
                    dashboard_id=d_obj.id,
                    kpi_name=widget.kpi_name,
                    insight_type="STANDARD",
                    chart_type=widget.chart_type,
                    applicability="GLOBAL",
                    confidence=enrichment.confidence_score,
                    confidence_score=enrichment.confidence_score,
                    generation_source="AI",
                    prompt_version=SemanticPromptBuilder.PROMPT_VERSION,
                    review_status=review_status
                ))
            
        # Questions
        for q in enrichment.questions:
            db.add(SuggestedQuestion(
                semantic_model_id=semantic_model_id,
                entity_name=q.entity_name,
                question=q.question,
                filter_logic=q.filter_logic,
                confidence=enrichment.confidence_score,
                confidence_score=enrichment.confidence_score,
                generation_source="AI",
                prompt_version=SemanticPromptBuilder.PROMPT_VERSION,
                review_status=review_status
            ))
            
        # AI Context
        db.add(AIContext(
            semantic_model_id=semantic_model_id,
            purpose=enrichment.ai_context.purpose,
            default_filters=enrichment.ai_context.default_filters,
            time_intelligence=enrichment.ai_context.time_intelligence,
            chart_preferences=enrichment.ai_context.chart_preferences,
            context_payload=enrichment.model_dump(exclude={"ontology", "kpis", "dashboards", "questions"}),
            confidence=enrichment.confidence_score,
            confidence_score=enrichment.confidence_score,
            generation_source="AI",
            prompt_version=SemanticPromptBuilder.PROMPT_VERSION,
            review_status=review_status
        ))
        
        db.commit()
