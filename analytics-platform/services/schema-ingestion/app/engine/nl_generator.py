from pydantic import BaseModel

from app.engine.executor_service import ExecutorResult
from app.llm.provider import get_llm_provider
from app.schemas_engine import LogicalQueryPlan


class NLExplanation(BaseModel):
    explanation: str

class NLGenerator:
    @staticmethod
    def generate_explanation(query: str, plan: LogicalQueryPlan, result: ExecutorResult) -> str:
        provider = get_llm_provider()

        # We only pass a sample of rows to the LLM to save tokens and prevent huge inputs
        data_sample = result.rows[:5]

        prompt = f"""
You are an expert Data Analyst.
A user asked: "{query}"

We executed a query with the following plan:
{plan.model_dump_json(indent=2)}

And got this data sample (first 5 rows):
{data_sample}

Generate a concise, natural language explanation of the results. 
Do not invent facts. State what metric was computed and the group by dimensions.
"""
        try:
            resp = provider.generate_structured(prompt, NLExplanation)
            return resp.explanation
        except Exception:
            return "Here are your results."
