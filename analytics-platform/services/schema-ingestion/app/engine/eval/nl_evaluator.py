from pydantic import BaseModel

from app.llm.orchestrator import ai_orchestrator


class NLEvaluationResult(BaseModel):
    score: float  # 0.0 to 1.0
    reason: str

class NLEvaluator:
    @staticmethod
    def evaluate(question: str, generated_answer: str, execution_result: dict) -> float:
        if not generated_answer:
            return 0.0


        prompt = f"""
You are an expert AI evaluator.
Evaluate the factual correctness and absence of hallucination in the generated answer.

USER QUESTION: {question}
ACTUAL DB RESULTS: {execution_result}
GENERATED ANSWER: {generated_answer}

Rate the answer from 0.0 to 1.0 based on factual correctness. Output JSON with 'score' and 'reason'.
"""
        try:
            res = ai_orchestrator.generate_structured(prompt, NLEvaluationResult)
            return float(res.score)
        except Exception:
            return 0.0
