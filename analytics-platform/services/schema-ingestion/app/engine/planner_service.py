from sqlalchemy.orm import Session

from app.engine.resolver_service import ResolutionResult
from app.engine.semantic_cache import semantic_cache
from app.llm.orchestrator import ai_orchestrator
from app.llm.prompts.semantic_prompts import SemanticPromptBuilder
from app.schemas_engine import NLUIntent, LogicalQueryPlan, PlannerLLMOutput, QueryPlanFilter


class PlannerService:
    @staticmethod
    def generate_plan(db: Session, intent: NLUIntent, resolution: ResolutionResult, rag_hits=None) -> LogicalQueryPlan:
        """
        Stage 2 - Advanced AI Query Planning Pipeline
        Context Builder -> Prompt Builder -> LLM -> Semantic Validation
        """
        # 1. Semantic Validation
        if not resolution.metric and not resolution.kpi:
            raise ValueError(f"Cannot generate plan without a valid metric or KPI. Unresolved: {intent.metric} / {intent.kpi}")

        # 2. Context Builder (via Semantic Cache)
        ai_context_payload = "{}"
        semantic_model_id = None
        
        if resolution.kpi:
            semantic_model_id = resolution.kpi.semantic_model_id
        elif resolution.metric:
            semantic_model_id = resolution.metric.semantic_model_id

        if semantic_model_id:
            ai_context_payload = semantic_cache.get_context(db, semantic_model_id)

        metric_ctx = ""
        if resolution.kpi:
            metric_ctx += f"KPI Name: {resolution.kpi.name}\nFormula: {resolution.kpi.formula}\n\n"
        if resolution.metric:
            metric_ctx += f"Metric Name: {resolution.metric.name}\nExpression: {resolution.metric.expression}\n\n"

        dim_ctx = "Available Resolved Dimensions:\n"
        for dim in resolution.dimensions:
            dim_ctx += f"- {dim.business_name}\n"

        # 3. Prompt Builder
        prompt = SemanticPromptBuilder.build_query_planner_prompt(
            intent_json=intent.model_dump_json(indent=2),
            metric_ctx=metric_ctx,
            dim_ctx=dim_ctx,
            ai_context_payload=ai_context_payload
        )

        if rag_hits and rag_hits.used_rag:
            rag_context = "Top Retrieved Tables:\n"
            for t, dist in rag_hits.tables:
                rag_context += f"- {t.table_name}: {t.description} (dist: {dist:.3f})\n"
            rag_context += "\nTop Glossary Terms:\n"
            for g, dist in rag_hits.glossary:
                rag_context += f"- {g.term}: {g.business_definition} (dist: {dist:.3f})\n"
            if hasattr(rag_hits, 'approved_examples') and rag_hits.approved_examples:
                rag_context += "\nApproved Query Examples (Few-Shot Context):\n"
                for ex, dist in rag_hits.approved_examples:
                    rag_context += f"- Q: {ex.question}\n  SQL: {ex.generated_sql} (dist: {dist:.3f})\n"
            prompt += f"\n\nRETRIEVED VECTOR CONTEXT (RAG):\n{rag_context}\nUse this context to better understand business terminology, relevant tables, and past approved SQL examples."

        # 4. LLM -> 5. Semantic Validation (Pydantic parsing)
        llm_out = ai_orchestrator.generate_structured(prompt, PlannerLLMOutput)
        
        # 6. Map string names back to UUIDs
        kpi_ids = []
        for name in llm_out.kpi_names:
            if resolution.kpi and resolution.kpi.name.lower() == name.lower():
                kpi_ids.append(resolution.kpi.id)
            else:
                raise ValueError(f"LLM referenced unknown KPI: {name}")
                
        metric_ids = []
        for name in llm_out.metric_names:
            if resolution.metric and resolution.metric.name.lower() == name.lower():
                metric_ids.append(resolution.metric.id)
            else:
                raise ValueError(f"LLM referenced unknown Metric: {name}")
                
        dim_map = {d.business_name.lower(): d.id for d in resolution.dimensions}
        
        dimension_ids = []
        for name in llm_out.dimension_names:
            did = dim_map.get(name.lower())
            if not did:
                if name.lower() in ["day", "week", "month", "quarter", "year", "date", "time", "hour", "minute"]:
                    llm_out.time_granularity = name.lower()
                    continue
                raise ValueError(f"LLM referenced unknown Dimension: {name}")
            dimension_ids.append(did)
            
        filters = []
        for f in llm_out.filters:
            did = dim_map.get(f.column_name.lower())
            if not did:
                raise ValueError(f"LLM referenced unknown Dimension in filter: {f.column_name}")
            filters.append(QueryPlanFilter(column_id=did, operator=f.operator, value=f.value))
            
        sort_column_id = None
        if llm_out.sort_column_name:
            did = dim_map.get(llm_out.sort_column_name.lower())
            if did:
                sort_column_id = did
            elif resolution.metric and resolution.metric.name.lower() == llm_out.sort_column_name.lower():
                sort_column_id = resolution.metric.id
            elif resolution.kpi and resolution.kpi.name.lower() == llm_out.sort_column_name.lower():
                sort_column_id = resolution.kpi.id
            else:
                if llm_out.sort_column_name.lower() in ["day", "week", "month", "quarter", "year", "date", "time", "hour", "minute"]:
                    sort_column_id = None
                else:
                    raise ValueError(f"LLM referenced unknown sort column: {llm_out.sort_column_name}")
                
        return LogicalQueryPlan(
            intent=llm_out.intent,
            kpi_ids=kpi_ids,
            metric_ids=metric_ids,
            dimension_ids=dimension_ids,
            filters=filters,
            time_granularity=llm_out.time_granularity,
            time_intelligence=llm_out.time_intelligence,
            sort_column_id=sort_column_id,
            sort_direction=llm_out.sort_direction,
            limit=llm_out.limit,
            chart_recommendation=llm_out.chart_recommendation,
            confidence_score=llm_out.confidence_score,
            reasoning=llm_out.reasoning
        )
