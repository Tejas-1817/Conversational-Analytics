class ChartEvaluator:
    @staticmethod
    def evaluate(expected: str, generated: str) -> float:
        if not expected or not generated:
            return 0.0

        expected_norm = expected.lower().strip().replace(" ", "_").replace("-", "_")
        generated_norm = generated.lower().strip().replace(" ", "_").replace("-", "_")

        if expected_norm == generated_norm:
            return 1.0

        return 0.0
