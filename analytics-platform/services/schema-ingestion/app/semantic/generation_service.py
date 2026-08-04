import concurrent.futures
import structlog
import uuid
import datetime
import time
import statistics
from tenacity import retry, stop_after_attempt, wait_exponential
from sqlalchemy.orm import Session, selectinload

from app.models import (
    TableMeta, ColumnMeta, SemanticDimension, SemanticMetric,
    BusinessGlossary, SemanticJoin, SemanticKPI, Relationship,
    BusinessOntology, DashboardRecommendation, SuggestedQuestion,
    AIContext, ChartRecommendation
)
from app.llm.orchestrator import ai_orchestrator
from app.semantic.context_builder import BusinessContextBuilder
from app.llm.prompts.semantic_prompts import SemanticPromptBuilder
from app.schemas_semantic_ai import AITableEnrichmentSchema, AIGlobalEnrichmentSchema, AITableDimensionsSchema, AITableMeasuresSchema, AITableMetadataSchema
from app.semantic.validation_service import SemanticValidationService
from app.schemas_validation import ValidationStatus

logger = structlog.get_logger(__name__)

class SemanticGenerationService:
    """
    A modular, robust semantic generation service that processes tables individually.
    Handles per-table isolation, retries, and persistence to ensure fault-tolerance.
    """

    @classmethod
    def generate_for_tables(
        cls,
        db: Session,
        tables: list[TableMeta],
        tenant_id: uuid.UUID,
        semantic_model_id: uuid.UUID,
        max_workers: int = 3
    ):
        """
        Executes semantic generation for each table. 
        Failures in one table will not affect the successful persistence of others.
        """
        if not tables:
            return {}, []

        logger.info("starting_semantic_generation_pipeline", table_count=len(tables), max_workers=max_workers)

        metrics = {
            "tables_processed": len(tables),
            "tables_succeeded": 0,
            "tables_failed": 0,
            "llm_requests": len(tables),
            "llm_successes": 0,
            "llm_failures": 0,
            "avg_latency_context_ms": 0,
            "avg_latency_llm_ms": 0,
            "avg_latency_validation_ms": 0,
            "p95_total_latency_ms": 0,
            "slowest_tables": [],
            "avg_prompt_size_chars": 0,
            "avg_token_estimate": 0,
            "validation_failures": {},
            "kpis_generated": 0,
            "kpi_generation_success_rate": 0.0
        }
        warnings = []
        table_stats = []

        def _process_single_table(table: TableMeta):
            try:
                result = cls._generate_and_persist_table(
                    db, table.id, tenant_id, semantic_model_id
                )
                result["table_name"] = table.table_name
                return result
            except Exception as e:
                provider_name = getattr(ai_orchestrator.provider, "__class__", type(ai_orchestrator.provider)).__name__ if ai_orchestrator.provider else "unknown"
                logger.error("fatal_table_generation_error", table_id=str(table.id), error=str(e))
                return {
                    "success": False,
                    "table_name": table.table_name,
                    "warning": {
                        "stage": "semantic_generation",
                        "table": table.table_name,
                        "provider": provider_name,
                        "error_type": type(e).__name__,
                        "message": str(e),
                        "recoverable": False,
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "attempt": 1
                    },
                    "llm_successes": 0,
                    "llm_failures": 3,
                    "total_latency_ms": 0,
                    "context_latency_ms": 0,
                    "llm_latency_ms": 0,
                    "validation_latency_ms": 0,
                    "prompt_size_chars": 0,
                    "validation_failures": {},
                    "kpis_generated": 0,
                    "kpis_failed": 0
                }

        if max_workers == 3:
            for table in tables:
                res = _process_single_table(table)
                table_stats.append(res)
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_task = [executor.submit(_process_single_table, t) for t in tables]
                for future in concurrent.futures.as_completed(future_to_task):
                    table_stats.append(future.result())

        # Aggregate Metrics
        total_context_ms = 0
        total_llm_ms = 0
        total_validation_ms = 0
        total_prompts_chars = 0
        all_latencies = []
        kpis_failed_total = 0

        for stat in table_stats:
            metrics["llm_successes"] += stat.get("llm_successes", 0)
            metrics["llm_failures"] += stat.get("llm_failures", 0)
            metrics["kpis_generated"] += stat.get("kpis_generated", 0)
            kpis_failed_total += stat.get("kpis_failed", 0)
            
            if stat.get("success"):
                metrics["tables_succeeded"] += 1
            else:
                metrics["tables_failed"] += 1
                
            if stat.get("warning"):
                warnings.append(stat.get("warning"))
                
            for fail_type, count in stat.get("validation_failures", {}).items():
                metrics["validation_failures"][fail_type] = metrics["validation_failures"].get(fail_type, 0) + count

            total_context_ms += stat.get("context_latency_ms", 0)
            total_llm_ms += stat.get("llm_latency_ms", 0)
            total_validation_ms += stat.get("validation_latency_ms", 0)
            total_prompts_chars += stat.get("prompt_size_chars", 0)
            
            if stat.get("total_latency_ms", 0) > 0:
                all_latencies.append((stat.get("table_name", "unknown"), stat.get("total_latency_ms", 0)))

        metrics["llm_requests"] = metrics["llm_successes"] + metrics["llm_failures"]

        num_stats = len(table_stats)
        if num_stats > 0:
            metrics["avg_latency_context_ms"] = int(total_context_ms / num_stats)
            metrics["avg_latency_llm_ms"] = int(total_llm_ms / num_stats)
            metrics["avg_latency_validation_ms"] = int(total_validation_ms / num_stats)
            metrics["avg_prompt_size_chars"] = int(total_prompts_chars / num_stats)
            metrics["avg_token_estimate"] = int((total_prompts_chars / num_stats) / 4)
            
            lat_vals = [l[1] for l in all_latencies]
            if lat_vals:
                lat_vals.sort()
                p95_idx = int(len(lat_vals) * 0.95)
                metrics["p95_total_latency_ms"] = lat_vals[min(p95_idx, len(lat_vals)-1)]
                
                # Slowest tables (top 5)
                all_latencies.sort(key=lambda x: x[1], reverse=True)
                metrics["slowest_tables"] = [{"table": t[0], "latency_ms": t[1]} for t in all_latencies[:5]]

        total_kpis = metrics["kpis_generated"] + kpis_failed_total
        if total_kpis > 0:
            metrics["kpi_generation_success_rate"] = round(metrics["kpis_generated"] / total_kpis, 4)
            
        logger.info("finished_semantic_generation_pipeline", metrics=metrics)
        return metrics, warnings

    @classmethod
    def _generate_and_persist_table(
        cls, 
        db: Session, 
        table_id: uuid.UUID, 
        tenant_id: uuid.UUID, 
        semantic_model_id: uuid.UUID
    ):
        """
        Generates and persists semantic objects for a single table.
        Creates a new DB session/transaction to isolate failures.
        """
        table = db.query(TableMeta).options(selectinload(TableMeta.columns)).filter(TableMeta.id == table_id).first()
        if not table:
            return {"success": False}
            
        stats = {
            "success": False,
            "warning": None,
            "llm_successes": 0,
            "llm_failures": 0,
            "context_latency_ms": 0,
            "llm_latency_ms": 0,
            "validation_latency_ms": 0,
            "total_latency_ms": 0,
            "prompt_size_chars": 0,
            "validation_failures": {},
            "kpis_generated": 0,
            "kpis_failed": 0
        }
        
        t_start_total = time.perf_counter()
        
        # Check if already processed (Caching and Regenerating Avoidance)
        existing_dims_count = db.query(SemanticDimension).filter(SemanticDimension.semantic_model_id == semantic_model_id, SemanticDimension.source_table_id == table.id).count()
        existing_metrics_count = db.query(SemanticMetric).filter(SemanticMetric.semantic_model_id == semantic_model_id, SemanticMetric.source_table_id == table.id).count()
        
        if existing_dims_count > 0 and existing_metrics_count > 0:
            # Skip generation for unchanged table
            stats["success"] = True
            stats["total_latency_ms"] = int((time.perf_counter() - t_start_total) * 1000)
            return stats

        # 1. Context Build
        t0 = time.perf_counter()
        context_json = BusinessContextBuilder.build_table_context(db, table_id)
        stats["context_latency_ms"] = int((time.perf_counter() - t0) * 1000)
        
        @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
        def _generate_with_retry(prompt, schema):
            return ai_orchestrator.generate_structured(prompt=prompt, schema=schema)
        
        # 2. LLM Generation
        t0 = time.perf_counter()
        try:
            prompt = SemanticPromptBuilder.build_table_enrichment_prompt(context_json, target_type="ALL")
            stats["prompt_size_chars"] = len(prompt)

            enrichment: AITableEnrichmentSchema = _generate_with_retry(prompt=prompt, schema=AITableEnrichmentSchema)
            stats["llm_successes"] += 1

        except Exception as e:
            stats["llm_failures"] = 1 - stats["llm_successes"]
            stats["llm_latency_ms"] = int((time.perf_counter() - t0) * 1000)
            stats["total_latency_ms"] = int((time.perf_counter() - t_start_total) * 1000)
            logger.error("table_enrichment_llm_failed", table=table.table_name, error=str(e))
            provider_name = getattr(ai_orchestrator.provider, "__class__", type(ai_orchestrator.provider)).__name__ if ai_orchestrator.provider else "unknown"
            stats["warning"] = {
                "stage": "semantic_generation",
                "table": table.table_name,
                "provider": provider_name,
                "error_type": type(e).__name__,
                "message": str(e),
                "recoverable": False,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "attempt": 1
            }
            return stats
            
        stats["llm_latency_ms"] = int((time.perf_counter() - t0) * 1000)

        # 3. Validation & Persistence
        t0 = time.perf_counter()
        try:
            val_failures, kpis_gen, kpis_fail = cls._persist_table_fragments(db, table, tenant_id, semantic_model_id, enrichment)
            stats["validation_failures"] = val_failures
            stats["kpis_generated"] = kpis_gen
            stats["kpis_failed"] = kpis_fail
            stats["success"] = True
        except Exception as e:
            db.rollback()
            logger.error("table_persistence_failed", table=table.table_name, error=str(e))
            stats["warning"] = {
                "stage": "semantic_persistence",
                "table": table.table_name,
                "error_type": type(e).__name__,
                "message": str(e),
                "recoverable": False,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
            
        stats["validation_latency_ms"] = int((time.perf_counter() - t0) * 1000)
        stats["total_latency_ms"] = int((time.perf_counter() - t_start_total) * 1000)
        
        return stats

    @classmethod
    def _persist_table_fragments(
        cls,
        db: Session,
        table: TableMeta,
        tenant_id: uuid.UUID,
        semantic_model_id: uuid.UUID,
        enrichment: AITableEnrichmentSchema
    ):
        """
        Isolated persistence of semantic metadata for a single table.
        """
        # Run Validation Engine First
        enrichment, report = SemanticValidationService.validate_table_enrichment(db, table, enrichment)
        
        # Log validation results
        logger.info("table_validation_complete", table_id=str(table.id), report=report.model_dump())
        
        # Map object names to their status for fast lookup during persistence
        status_map = {r.object_name: r.status for r in report.results}
        
        val_failures = {}
        for r in report.results:
            if r.status != ValidationStatus.VALIDATED:
                msg = r.message or "Unknown Validation Error"
                val_failures[msg] = val_failures.get(msg, 0) + 1
        
        def get_review_status(object_name: str) -> str:
            status = status_map.get(object_name, ValidationStatus.VALIDATED)
            if status == ValidationStatus.VALIDATED:
                return "ACTIVE"
            return "REVIEW_REQUIRED"

        if enrichment.business_description and not table.description:
            table.description = enrichment.business_description

        # Fast maps for matching
        col_map = {c.column_name.lower(): c for c in (table.columns or [])}
        
        # Determine existing columns to avoid duplicates
        existing_dims = {
            r[0] for r in db.query(SemanticDimension.source_column_id)
            .filter(SemanticDimension.semantic_model_id == semantic_model_id, SemanticDimension.source_table_id == table.id).all()
        }
        existing_metrics = {
            r[0] for r in db.query(SemanticMetric.source_column_id)
            .filter(SemanticMetric.semantic_model_id == semantic_model_id, SemanticMetric.source_table_id == table.id, SemanticMetric.is_calculated == False).all()
        }
        
        existing_kpis = {
            r[0] for r in db.query(SemanticKPI.name)
            .filter(SemanticKPI.semantic_model_id == semantic_model_id).all()
        }
        
        existing_terms = {
            r[0] for r in db.query(BusinessGlossary.term)
            .filter(BusinessGlossary.semantic_model_id == semantic_model_id).all()
        }
        
        all_tables = db.query(TableMeta).options(selectinload(TableMeta.columns)).filter(TableMeta.source_id == table.source_id).all()
        table_map = {t.table_name.lower(): t for t in all_tables}
        
        existing_joins = {
            (j.left_column_id, j.right_column_id) for j in db.query(SemanticJoin.left_column_id, SemanticJoin.right_column_id)
            .filter(SemanticJoin.semantic_model_id == semantic_model_id, SemanticJoin.left_table_id == table.id).all()
        }

        # 1. Dimensions
        for dim_schema in enrichment.dimensions:
            col = col_map.get(dim_schema.source_column_name.lower())
            if not col or col.id in existing_dims:
                continue
            
            is_time_col = any(t in col.data_type.lower() for t in ["date", "time", "timestamp"])
            time_granularity = dim_schema.time_granularity if is_time_col else "NONE"
            
            db.add(SemanticDimension(
                tenant_id=tenant_id,
                semantic_model_id=semantic_model_id,
                business_name=dim_schema.business_name,
                description=dim_schema.description,
                source_table_id=table.id,
                source_column_id=col.id,
                data_type=col.data_type,
                is_time_dimension=is_time_col,
                time_granularity=time_granularity,
                created_by="ai_generator",
                updated_by="ai_generator",
                generation_source="AI",
                confidence_score=enrichment.confidence_score,
                prompt_version=SemanticPromptBuilder.PROMPT_VERSION,
                review_status=get_review_status(dim_schema.business_name)
            ))

        # 2. Measures
        valid_aggs = {"SUM", "AVG", "COUNT", "COUNT_DISTINCT", "MIN", "MAX", "CUSTOM"}
        for measure_schema in enrichment.measures:
            col = col_map.get(measure_schema.source_column_name.lower())
            if not col or col.id in existing_metrics:
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
                review_status=get_review_status(measure_schema.business_name)
            ))

        # 3. KPIs
        for kpi_schema in enrichment.kpis:
            if kpi_schema.business_name in existing_kpis:
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
                review_status=get_review_status(kpi_schema.business_name)
            ))

        # 4. Glossary Terms
        for term_schema in enrichment.glossary_terms:
            if term_schema.term in existing_terms:
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
                review_status=get_review_status(term_schema.term)
            ))

        # 5. Relationships (Deterministic based on physical keys)
        # Fetch physical relationships originating from this table
        outbound_rels = db.query(Relationship).filter(
            Relationship.from_column_id.in_([c.id for c in (table.columns or [])])
        ).all()
        
        for rel in outbound_rels:
            local_col = next((c for c in (table.columns or []) if c.id == rel.from_column_id), None)
            if not local_col:
                continue
                
            # We must load the target column's table to get its name and id
            target_col = db.query(ColumnMeta).options(selectinload(ColumnMeta.table)).filter(ColumnMeta.id == rel.to_column_id).first()
            if not target_col or not target_col.table:
                continue
                
            if (local_col.id, target_col.id) in existing_joins:
                continue

            db.add(SemanticJoin(
                tenant_id=tenant_id,
                semantic_model_id=semantic_model_id,
                left_table_id=table.id,
                left_column_id=local_col.id,
                right_table_id=target_col.table.id,
                right_column_id=target_col.id,
                join_type="LEFT",
                join_condition=f"{{{{ {table.table_name}.{local_col.column_name} }}}} = {{{{ {target_col.table.table_name}.{target_col.column_name} }}}}",
                cardinality=rel.cardinality or "many_to_one",
                created_by="system",
                updated_by="system",
                generation_source="AI",
                confidence=1.0,
                prompt_version="v1.0",
                review_status="ACTIVE"
            ))

        # Commit fragment for this table
        db.commit()
        
        # Calculate KPI success
        kpis_gen = 0
        kpis_fail = 0
        for k in enrichment.kpis:
            if status_map.get(k.business_name) == ValidationStatus.VALIDATED:
                kpis_gen += 1
            else:
                kpis_fail += 1
                
        return val_failures, kpis_gen, kpis_fail

    @classmethod
    def generate_global(cls, db: Session, source_id: uuid.UUID, semantic_model_id: uuid.UUID):
        """
        Global enrichment remains mostly unchanged but uses the new service abstraction.
        """
        from app.semantic.enrichment_service import SemanticEnrichmentService
        return SemanticEnrichmentService.enrich_global(db, source_id, semantic_model_id)
