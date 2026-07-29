import uuid
import pytest
from unittest.mock import MagicMock, patch

from app.engine.query_intelligence_service import QueryIntelligenceService
from app.schemas_engine import QueryIntelligenceOutput
from app.engine.retrieval_service import RetrievalHits
from app.models import SemanticMetric, SemanticDimension, TableMeta

@pytest.fixture
def mock_db():
    return MagicMock()

def test_query_intelligence_no_context(mock_db):
    with patch('app.engine.query_intelligence_service.RetrievalService.retrieve') as mock_retrieve:
        mock_retrieve.return_value = RetrievalHits() # Empty hits
        
        result = QueryIntelligenceService.answer_question(mock_db, uuid.uuid4(), "What is the meaning of life?")
        
        assert result["sql"] is None
        assert "enough semantic context" in result["explanation"]

def test_query_intelligence_success(mock_db):
    tenant_id = uuid.uuid4()
    with patch('app.engine.query_intelligence_service.RetrievalService.retrieve') as mock_retrieve, \
         patch('app.engine.query_intelligence_service.ai_orchestrator.generate_structured') as mock_generate, \
         patch('app.engine.query_intelligence_service.ExecutorService.execute') as mock_execute:
        
        # Mock Semantic Objects
        metric = SemanticMetric(name="total_revenue", business_name="Total Revenue", expression="SUM(revenue)")
        dim = SemanticDimension(business_name="Region", source_column_id=uuid.uuid4())
        tbl = TableMeta(table_name="sales", schema_name="public", id=uuid.uuid4())
        
        hits = RetrievalHits(
            metrics=[(metric, 0.1)],
            dimensions=[(dim, 0.1)],
            tables=[(tbl, 0.1)],
            glossary=[]
        )
        mock_retrieve.return_value = hits
        
        # Mock LLM Output
        mock_generate.return_value = QueryIntelligenceOutput(
            sql="SELECT SUM(revenue) FROM sales WHERE tenant_id = :tenant_id GROUP BY region",
            explanation="Calculated total revenue grouped by region.",
            referenced_semantics=["Total Revenue", "Region"],
            confidence=0.95
        )
        
        # Mock DB Execution
        mock_exec_result = MagicMock()
        mock_exec_result.columns = ["region", "revenue"]
        mock_exec_result.rows = [{"region": "NA", "revenue": 100}]
        mock_exec_result.execution_time_ms = 15
        mock_execute.return_value = mock_exec_result
        
        result = QueryIntelligenceService.answer_question(mock_db, tenant_id, "Show revenue by region")
        
        assert result["sql"] == "SELECT SUM(revenue) FROM sales WHERE tenant_id = :tenant_id GROUP BY region"
        assert result["confidence"] == 0.95
        assert result["execution_metadata"]["rows"][0]["region"] == "NA"

def test_query_intelligence_unsafe_sql(mock_db):
    tenant_id = uuid.uuid4()
    with patch('app.engine.query_intelligence_service.RetrievalService.retrieve') as mock_retrieve, \
         patch('app.engine.query_intelligence_service.ai_orchestrator.generate_structured') as mock_generate:
        
        metric = SemanticMetric(name="total_revenue", business_name="Total Revenue", expression="SUM(revenue)")
        hits = RetrievalHits(metrics=[(metric, 0.1)])
        mock_retrieve.return_value = hits
        
        # Mock LLM Output with unsafe SQL
        mock_generate.return_value = QueryIntelligenceOutput(
            sql="DROP TABLE sales;",
            explanation="Dropped the table as requested.",
            referenced_semantics=[],
            confidence=0.9
        )
        
        result = QueryIntelligenceService.answer_question(mock_db, tenant_id, "Drop the sales table")
        
        assert result["sql"] is None
        assert "rejected for safety reasons" in result["explanation"]
