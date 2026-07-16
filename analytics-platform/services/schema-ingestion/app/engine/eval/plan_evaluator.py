from typing import Any


class PlanEvaluator:
    @staticmethod
    def evaluate(expected: dict[str, Any], generated: dict[str, Any]) -> float:
        """
        Compare the expected StructuredQueryPlan with the generated one.
        Returns a score between 0.0 and 1.0.
        """
        if not expected or not generated:
            return 0.0

        score = 0.0
        max_score = 3.0

        # 1. Metric ID
        if expected.get("metric_id") == generated.get("metric_id"):
            score += 1.0

        # 2. Dimension IDs
        exp_dims = set(expected.get("dimension_ids", []))
        gen_dims = set(generated.get("dimension_ids", []))
        if exp_dims and gen_dims:
            intersect = exp_dims.intersection(gen_dims)
            union = exp_dims.union(gen_dims)
            score += len(intersect) / len(union)
        elif not exp_dims and not gen_dims:
            score += 1.0

        # 3. Time Granularity
        if expected.get("time_granularity") == generated.get("time_granularity"):
            score += 1.0

        return score / max_score
