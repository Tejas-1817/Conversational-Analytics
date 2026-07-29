import pytest
import uuid
from unittest.mock import patch, MagicMock

from app.schemas_benchmark import BenchmarkTestCase
from app.engine.eval.benchmark_runner import BenchmarkRunnerService
from app.engine.retrieval_service import RetrievalHits
from app.models import SemanticMetric, SemanticDimension

@pytest.fixture
def mock_db():
    return MagicMock()

def test_benchmark_runner_success(mock_db):
    tenant_id = uuid.uuid4()
    
    test_cases = [
        BenchmarkTestCase(
            id="test_001",
            question="Show employee headcount by department",
            domain="HR",
            expected_semantic_objects=["Employee Headcount", "Department"],
            expected_columns=["department", "headcount"]
        )
    ]
    
    with patch('app.engine.eval.benchmark_runner.RetrievalService.retrieve') as mock_retrieve, \
         patch('app.engine.eval.benchmark_runner.QueryIntelligenceService.answer_question') as mock_answer:
        
        # Mock retrieval returning exactly what we need
        m = SemanticMetric(name="employee_headcount", business_name="Employee Headcount")
        d = SemanticDimension(business_name="Department")
        mock_retrieve.return_value = RetrievalHits(metrics=[(m, 1.0)], dimensions=[(d, 1.0)], tables=[], glossary=[])
        
        # Mock successful AI generation
        mock_answer.return_value = {
            "sql": "SELECT department, COUNT(id) as headcount FROM employees GROUP BY department",
            "explanation": "Grouping by department",
            "referenced_semantics": ["Employee Headcount", "Department"],
            "confidence": 0.95,
            "execution_metadata": {
                "columns": ["department", "headcount"]
            }
        }
        
        report = BenchmarkRunnerService.run_benchmark(mock_db, tenant_id, test_cases)
        
        assert report.total_test_cases == 1
        assert report.success_rate == 1.0
        assert report.avg_retrieval_precision == 1.0
        assert report.avg_retrieval_recall == 1.0
        assert report.hallucination_rate == 0.0
        assert report.safety_violation_rate == 0.0
        assert report.sql_validity_rate == 1.0
        assert report.execution_success_rate == 1.0
        assert report.schema_match_rate == 1.0
        assert report.avg_calibration_error == pytest.approx(0.05, 0.01) # 1.0 success - 0.95 confidence
        
def test_benchmark_runner_hallucination(mock_db):
    tenant_id = uuid.uuid4()
    
    test_cases = [
        BenchmarkTestCase(
            id="test_002",
            question="Total revenue",
            domain="Sales",
            expected_semantic_objects=["Total Revenue"]
        )
    ]
    
    with patch('app.engine.eval.benchmark_runner.RetrievalService.retrieve') as mock_retrieve, \
         patch('app.engine.eval.benchmark_runner.QueryIntelligenceService.answer_question') as mock_answer:
        
        # Mock retrieval returning Total Revenue
        m = SemanticMetric(name="total_revenue", business_name="Total Revenue")
        mock_retrieve.return_value = RetrievalHits(metrics=[(m, 1.0)], dimensions=[], tables=[], glossary=[])
        
        # Mock AI generation hallucinating a "Profit" metric not provided
        mock_answer.return_value = {
            "sql": "SELECT revenue, profit FROM sales",
            "explanation": "Here is revenue and profit",
            "referenced_semantics": ["Total Revenue", "Profit Margin"], # Hallucinated Profit Margin
            "confidence": 0.9,
            "execution_metadata": {
                "columns": ["revenue", "profit"]
            }
        }
        
        report = BenchmarkRunnerService.run_benchmark(mock_db, tenant_id, test_cases)
        
        assert report.total_test_cases == 1
        assert report.success_rate == 0.0
        assert report.hallucination_rate == 1.0
        assert "Hallucination" in report.failure_reasons
        assert report.failure_reasons["Hallucination"] == 1
        
        # Calibration error should be high because confidence was 0.9, but actual success is 0 (due to hallucination)
        assert report.avg_calibration_error == 0.9
