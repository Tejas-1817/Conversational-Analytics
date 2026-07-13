class ReliabilityScorer:
    @staticmethod
    def calculate_score(intent: float, plan: float, sql: float, result: float, chart: float, nl: float) -> float:
        """
        Weights based on BRD:
        Intent: 20%
        Plan (Semantic): 20%
        SQL: 20%
        Result: 20% (Adding Result as 20% to balance, keeping Chart 10%, NL 10%)
        """
        # Handling None values by defaulting to 0.0
        intent = intent or 0.0
        plan = plan or 0.0
        sql = sql or 0.0
        result = result or 0.0
        chart = chart or 0.0
        nl = nl or 0.0
        
        score = (intent * 0.20) + (plan * 0.20) + (sql * 0.20) + (result * 0.20) + (chart * 0.10) + (nl * 0.10)
        return min(max(score, 0.0), 1.0)
