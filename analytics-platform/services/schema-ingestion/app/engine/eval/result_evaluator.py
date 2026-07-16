from typing import Any


class ResultEvaluator:
    @staticmethod
    def evaluate(expected: dict[str, Any], generated: dict[str, Any]) -> float:
        """
        Compare expected result JSON against generated result JSON.
        Since exact matching is brittle, we compare row count and columns.
        """
        if not expected or not generated:
            return 0.0

        exp_rows = expected.get("rows", [])
        gen_rows = generated.get("rows", [])

        exp_cols = expected.get("columns", [])
        gen_cols = generated.get("columns", [])

        score = 0.0
        max_score = 2.0

        # 1. Row count match
        if len(exp_rows) == len(gen_rows):
            score += 1.0

        # 2. Column match
        if set(exp_cols) == set(gen_cols):
            score += 1.0

        return score / max_score
