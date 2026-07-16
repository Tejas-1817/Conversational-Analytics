from typing import Any


class IntentEvaluator:
    @staticmethod
    def evaluate(expected: dict[str, Any], generated: dict[str, Any]) -> float:
        """
        Compare the expected NLUIntent with the generated one.
        Returns a score between 0.0 and 1.0.
        """
        if not expected or not generated:
            return 0.0

        score = 0.0
        max_score = 5.0

        # 1. Intent type (e.g. "query")
        if expected.get("intent") == generated.get("intent"):
            score += 1.0

        # 2. Metric
        if expected.get("metric") == generated.get("metric"):
            score += 1.0

        # 3. Dimensions
        exp_dims = set(expected.get("dimensions", []))
        gen_dims = set(generated.get("dimensions", []))
        if exp_dims and gen_dims:
            intersect = exp_dims.intersection(gen_dims)
            union = exp_dims.union(gen_dims)
            score += len(intersect) / len(union)
        elif not exp_dims and not gen_dims:
            score += 1.0

        # 4. Time Granularity
        if expected.get("time_granularity") == generated.get("time_granularity"):
            score += 1.0

        # 5. Filters (simple check, assume exact match for now)
        exp_filters = expected.get("filters", [])
        gen_filters = generated.get("filters", [])
        if len(exp_filters) == len(gen_filters):
            score += 1.0

        return score / max_score
