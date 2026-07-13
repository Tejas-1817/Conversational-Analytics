from app.llm.provider import get_llm_provider
from app.schemas_engine import StructuredQueryPlan, NLUIntent
from app.engine.resolver_service import ResolutionResult

class PlannerService:
    @staticmethod
    def generate_plan(intent: NLUIntent, resolution: ResolutionResult) -> StructuredQueryPlan:
        # If no metric resolved, we cannot proceed with a data query.
        if not resolution.metric:
            raise ValueError(f"Cannot generate plan without a valid metric. Unresolved: {intent.metric}")
            
        provider = get_llm_provider()
        
        # Build context for the LLM
        metric_ctx = f"Metric ID: {resolution.metric.id}\nName: {resolution.metric.name}\nExpression: {resolution.metric.expression}\n\n"
        
        dim_ctx = "Available Resolved Dimensions:\n"
        for dim in resolution.dimensions:
            dim_ctx += f"- {dim.business_name} (ID: {dim.id})\n"
            
        prompt = f"""
You are the Query Planner for a Conversational Analytics Engine.
Generate a structured query plan using ONLY the provided UUIDs.

USER INTENT:
{intent.model_dump_json(indent=2)}

SEMANTIC CONTEXT:
{metric_ctx}
{dim_ctx}

Instructions:
1. Map the intent metric to the provided Metric ID.
2. Map the intent dimensions to the provided Dimension IDs.
3. Map filters to column UUIDs. Since you only know Dimension IDs, map filters on dimensions to the corresponding Dimension ID.
4. DO NOT invent UUIDs. Only use those provided in the context.
"""
        
        result = provider.generate_structured(prompt, StructuredQueryPlan)
        return result
