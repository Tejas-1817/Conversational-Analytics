import concurrent.futures
import structlog
import uuid
from sqlalchemy.orm import Session, selectinload

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
    def enrich_tables_parallel(
        cls,
        db: Session,
        tables: list[TableMeta],
        tenant_id: uuid.UUID,
        semantic_model_id: uuid.UUID,
        max_workers: int = 3
    ):
        """
        Executes parallel LLM calls for all tables and persists results in a single batch
        with zero N+1 database queries.
        """
        if not tables:
            return

        logger.info("starting_parallel_table_enrichment", count=len(tables), max_workers=max_workers)

        # 1. Build context prompts for all tables up-front
        tasks = []
        for t in tables:
            context_json = BusinessContextBuilder.build_table_context(db, t.id)
            prompt = SemanticPromptBuilder.build_table_enrichment_prompt(context_json)
            tasks.append((t, prompt))

        # 2. Execute LLM structured generations in parallel thread pool
        enrichment_results: list[tuple[TableMeta, AITableEnrichmentSchema]] = []

        def _call_llm(table_and_prompt):
            tbl, p_str = table_and_prompt
            try:
                enrichment_res: AITableEnrichmentSchema = ai_orchestrator.generate_structured(
                    prompt=p_str,
                    schema=AITableEnrichmentSchema
                )
                return tbl, enrichment_res, None
            except Exception as e:
                import datetime
                logger.error("table_enrichment_llm_failed", table=tbl.table_name, error=str(e))
                provider_name = getattr(ai_orchestrator.provider, "__class__", type(ai_orchestrator.provider)).__name__ if ai_orchestrator.provider else "unknown"
                warning = {
                    "stage": "semantic_generation",
                    "table": tbl.table_name,
                    "provider": provider_name,
                    "error_type": type(e).__name__,
                    "message": str(e),
                    "recoverable": False,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "attempt": 1
                }
                return tbl, None, warning

        warnings = []
        metrics = {
            "tables_processed": len(tables),
            "tables_succeeded": 0,
            "tables_failed": 0,
            "llm_requests": len(tables),
            "llm_successes": 0,
            "llm_failures": 0
        }
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = [executor.submit(_call_llm, task) for task in tasks]
            for future in concurrent.futures.as_completed(future_to_task):
                tbl, res, warning = future.result()
                if res is not None:
                    enrichment_results.append((tbl, res))
                    metrics["tables_succeeded"] += 1
                    metrics["llm_successes"] += 1
                else:
                    metrics["tables_failed"] += 1
                    metrics["llm_failures"] += 1
                
                if warning:
                    warnings.append(warning)

        # 3. Bulk Persist all enrichments in a single transaction with pre-fetched lookups
        cls._persist_bulk_table_enrichments(db, tenant_id, semantic_model_id, enrichment_results)
        logger.info("finished_parallel_table_enrichment", count=len(enrichment_results))
        return metrics, warnings

    @classmethod
    def _persist_bulk_table_enrichments(
        cls,
        db: Session,
        tenant_id: uuid.UUID,
        semantic_model_id: uuid.UUID,
        enrichments: list[tuple[TableMeta, AITableEnrichmentSchema]]
    ):
        if not enrichments:
            return

        # Pre-fetch existing entities to eliminate N+1 queries
        existing_dim_col_ids = {
            r[0] for r in db.query(SemanticDimension.source_column_id)
            .filter(SemanticDimension.semantic_model_id == semantic_model_id).all()
        }
        existing_metric_col_ids = {
            r[0] for r in db.query(SemanticMetric.source_column_id)
            .filter(SemanticMetric.semantic_model_id == semantic_model_id, SemanticMetric.is_calculated == False).all()
        }
        existing_kpi_names = {
            r[0] for r in db.query(SemanticKPI.name)
            .filter(SemanticKPI.semantic_model_id == semantic_model_id).all()
        }
        existing_glossary_terms = {
            r[0] for r in db.query(BusinessGlossary.term)
            .filter(BusinessGlossary.semantic_model_id == semantic_model_id).all()
        }
        existing_join_pairs = {
            (r[0], r[1]) for r in db.query(SemanticJoin.left_column_id, SemanticJoin.right_column_id)
            .filter(SemanticJoin.semantic_model_id == semantic_model_id).all()
        }

        first_table = enrichments[0][0]
        all_tables = db.query(TableMeta).options(selectinload(TableMeta.columns)).filter(TableMeta.source_id == first_table.source_id).all()
        table_map = {t.table_name.lower(): t for t in all_tables}

        # Global column lookup
        col_map_by_table: dict[uuid.UUID, dict[str, ColumnMeta]] = {}
        for t in all_tables:
            col_map_by_table[t.id] = {c.column_name.lower(): c for c in (t.columns or [])}

        for table, enrichment in enrichments:
            col_map = col_map_by_table.get(table.id, {})
            review_status = "ACTIVE" if enrichment.confidence_score >= 0.8 else "REVIEW_REQUIRED"

            if enrichment.business_description and not table.description:
                table.description = enrichment.business_description

            # Dimensions
            for dim_schema in enrichment.dimensions:
                col = col_map.get(dim_schema.source_column_name.lower())
                if not col or col.id in existing_dim_col_ids:
                    continue
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
                existing_dim_col_ids.add(col.id)

            # Measures
            valid_aggs = {"SUM", "AVG", "COUNT", "COUNT_DISTINCT", "MIN", "MAX", "CUSTOM"}
            for measure_schema in enrichment.measures:
                col = col_map.get(measure_schema.source_column_name.lower())
                if not col or col.id in existing_metric_col_ids:
                    continue
                raw_agg = (measure_schema.aggregation_type or "COUNT").upper()
                agg_type = raw_agg if raw_agg in valid_aggs else "COUNT"
                db.add(SemanticMetric(
                    tenant_id=tenant_id,
                    name=measure_schema.business_name,
                    description=measure_schema.description,
                    semantic_model_id=semantic_model_id,
                    is_calculated=False,
                    aggregation_type=agg_type,
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
                existing_metric_col_ids.add(col.id)

            # KPIs
            for kpi_schema in enrichment.kpis:
                if kpi_schema.business_name in existing_kpi_names:
                    continue
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
                existing_kpi_names.add(kpi_schema.business_name)

            # Glossary
            for term_schema in enrichment.glossary_terms:
                if term_schema.term in existing_glossary_terms:
                    continue
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
                existing_glossary_terms.add(term_schema.term)

            # Relationships
            for rel_schema in enrichment.relationships:
                local_col = col_map.get(rel_schema.from_column_name.lower())
                target_table = table_map.get(rel_schema.to_table_name.lower())
                if not local_col or not target_table:
                    continue

                target_cols = col_map_by_table.get(target_table.id, {})
                target_col = target_cols.get(rel_schema.to_column_name.lower())
                if not target_col or (local_col.id, target_col.id) in existing_join_pairs:
                    continue

                db.add(SemanticJoin(
                    tenant_id=tenant_id,
                    semantic_model_id=semantic_model_id,
                    left_table_id=table.id,
                    left_column_id=local_col.id,
                    right_table_id=target_table.id,
                    right_column_id=target_col.id,
                    join_type="LEFT",
                    join_condition=f"{{{{ {table.table_name}.{local_col.column_name} }}}} = {{{{ {target_table.table_name}.{target_col.column_name} }}}}",
                    cardinality=rel_schema.cardinality,
                    created_by="ai_generator",
                    updated_by="ai_generator",
                    generation_source="AI",
                    confidence=enrichment.confidence_score,
                    prompt_version=SemanticPromptBuilder.PROMPT_VERSION,
                    review_status=review_status
                ))
                existing_join_pairs.add((local_col.id, target_col.id))

        # Single atomic commit for all tables
        db.commit()

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
        cls._persist_bulk_table_enrichments(db, tenant_id, semantic_model_id, [(table, enrichment)])


    @classmethod
    def enrich_global(cls, db: Session, source_id: uuid.UUID, semantic_model_id: uuid.UUID):
        logger.info("starting_global_enrichment", source_id=str(source_id))
        
        context_json = BusinessContextBuilder.build_global_context(db, source_id)
        prompt = SemanticPromptBuilder.build_global_enrichment_prompt(context_json)
        
        metrics = {"llm_requests": 1, "llm_successes": 0, "llm_failures": 0}
        warnings = []
        
        try:
            enrichment: AIGlobalEnrichmentSchema = ai_orchestrator.generate_structured(
                prompt=prompt,
                schema=AIGlobalEnrichmentSchema
            )
            metrics["llm_successes"] = 1
            cls._persist_global_enrichment(db, semantic_model_id, enrichment)
            logger.info("finished_global_enrichment", source_id=str(source_id))
        except Exception as e:
            import datetime
            logger.error("global_enrichment_failed", source_id=str(source_id), error=str(e))
            metrics["llm_failures"] = 1
            provider_name = getattr(ai_orchestrator.provider, "__class__", type(ai_orchestrator.provider)).__name__ if ai_orchestrator.provider else "unknown"
            warnings.append({
                "stage": "semantic_generation_global",
                "table": None,
                "provider": provider_name,
                "error_type": type(e).__name__,
                "message": str(e),
                "recoverable": False,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "attempt": 1
            })
            
        return metrics, warnings

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
                confidence=enrichment.confidence_score
            )
            if review_status == "approved":
                d_obj.reviewed = True
                d_obj.approved = True
            db.add(d_obj)
            dashboard_objs.append((dash, d_obj))
            
        db.flush()
        
        for dash_schema, d_obj in dashboard_objs:
            for widget in dash_schema.widgets:
                chart = ChartRecommendation(
                    semantic_model_id=semantic_model_id,
                    dashboard_id=d_obj.id,
                    kpi_name=widget.kpi_name,
                    insight_type="STANDARD",
                    chart_type=widget.chart_type,
                    applicability="GLOBAL",
                    confidence=enrichment.confidence_score
                )
                if review_status == "approved":
                    chart.reviewed = True
                    chart.approved = True
                db.add(chart)
            
        # Questions
        for q in enrichment.questions:
            sq = SuggestedQuestion(
                semantic_model_id=semantic_model_id,
                entity_name=q.entity_name,
                question=q.question,
                filter_logic=q.filter_logic,
                confidence=enrichment.confidence_score
            )
            if review_status == "approved":
                sq.reviewed = True
                sq.approved = True
            db.add(sq)
            
        # AI Context
        ai = AIContext(
            semantic_model_id=semantic_model_id,
            purpose=enrichment.ai_context.purpose,
            default_filters=enrichment.ai_context.default_filters,
            time_intelligence=enrichment.ai_context.time_intelligence,
            chart_preferences=enrichment.ai_context.chart_preferences,
            context_payload=enrichment.model_dump(exclude={"ontology", "kpis", "dashboards", "questions"}),
            confidence=enrichment.confidence_score
        )
        if review_status == "approved":
            ai.reviewed = True
            ai.approved = True
        db.add(ai)
        
        db.commit()
