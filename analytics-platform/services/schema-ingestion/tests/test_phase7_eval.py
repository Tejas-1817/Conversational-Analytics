import uuid

from app.engine.eval.chart_evaluator import ChartEvaluator
from app.engine.eval.intent_evaluator import IntentEvaluator
from app.engine.eval.plan_evaluator import PlanEvaluator
from app.engine.eval.result_evaluator import ResultEvaluator
from app.engine.eval.scorer import ReliabilityScorer
from app.engine.eval.sql_evaluator import SQLEvaluator


class TestEvaluators:
    def test_intent_evaluator(self):
        expected = {"intent": "query", "metric": "revenue", "dimensions": ["region"]}
        generated = {"intent": "query", "metric": "revenue", "dimensions": ["region"]}
        score = IntentEvaluator.evaluate(expected, generated)
        assert score == 1.0

        gen2 = {"intent": "query", "metric": "revenue", "dimensions": []}
        score2 = IntentEvaluator.evaluate(expected, gen2)
        assert score2 == 0.8  # 4 out of 5 properties matched

    def test_plan_evaluator(self):
        m_id = str(uuid.uuid4())
        d_id = str(uuid.uuid4())
        expected = {"metric_id": m_id, "dimension_ids": [d_id], "time_granularity": None}
        generated = {"metric_id": m_id, "dimension_ids": [d_id], "time_granularity": None}
        score = PlanEvaluator.evaluate(expected, generated)
        assert score == 1.0

    def test_sql_evaluator(self):
        expected = "SELECT SUM(revenue) FROM sales GROUP BY region"
        generated = "SELECT SUM(revenue) \n FROM sales \n GROUP BY region"
        score = SQLEvaluator.evaluate(expected, generated)
        assert score == 1.0

        gen2 = "SELECT SUM(revenue) FROM sales"
        score2 = SQLEvaluator.evaluate(expected, gen2)
        assert score2 < 1.0

    def test_result_evaluator(self):
        expected = {"columns": ["region", "revenue"], "rows": [{"region": "NA", "revenue": 100}]}
        generated = {"columns": ["region", "revenue"], "rows": [{"region": "NA", "revenue": 100}]}
        assert ResultEvaluator.evaluate(expected, generated) == 1.0

    def test_chart_evaluator(self):
        assert ChartEvaluator.evaluate("bar_chart", "Bar Chart") == 1.0
        assert ChartEvaluator.evaluate("line_chart", "bar_chart") == 0.0

    def test_reliability_scorer(self):
        score = ReliabilityScorer.calculate_score(1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
        assert score == 1.0

        score2 = ReliabilityScorer.calculate_score(1.0, 1.0, 1.0, 1.0, 0.0, 0.0)
        assert score2 == 0.8
