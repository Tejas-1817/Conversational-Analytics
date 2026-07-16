from sqlalchemy.orm import Session

from app.engine.resolver_service import ResolutionResult
from app.engine.semantic_cache import semantic_cache
from app.llm.orchestrator import ai_orchestrator
from app.llm.prompts.semantic_prompts import SemanticPromptBuilder
from app.schemas_engine import NLUIntent, LogicalQueryPlan


class PlannerService:
    @staticmethod
    def generate_plan(db: Session, intent: NLUIntent, resolution: ResolutionResult) -> LogicalQueryPlan:
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
            metric_ctx += f"KPI ID: {resolution.kpi.id}\nName: {resolution.kpi.name}\nFormula: {resolution.kpi.formula}\n\n"
        if resolution.metric:
            metric_ctx += f"Metric ID: {resolution.metric.id}\nName: {resolution.metric.name}\nExpression: {resolution.metric.expression}\n\n"

        dim_ctx = "Available Resolved Dimensions:\n"
        for dim in resolution.dimensions:
            dim_ctx += f"- {dim.business_name} (ID: {dim.id})\n"

        # 3. Prompt Builder
        prompt = SemanticPromptBuilder.build_query_planner_prompt(
            intent_json=intent.model_dump_json(indent=2),
            metric_ctx=metric_ctx,
            dim_ctx=dim_ctx,
            ai_context_payload=ai_context_payload
        )

        # 4. LLM -> 5. Semantic Validation (Pydantic parsing)
        result = ai_orchestrator.generate_structured(prompt, LogicalQueryPlan)
        return result
