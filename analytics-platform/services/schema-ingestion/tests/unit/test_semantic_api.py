import pytest
import uuid
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app
from app.db import get_session
from app.api.deps import get_current_user
from app.models import SemanticMetric

client = TestClient(app)

class MockUser:
    id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    email = "analyst@example.com"
    role = "ANALYST"

class MockDB:
    def __init__(self):
        pass

@pytest.fixture(autouse=True)
def override_dependencies():
    app.dependency_overrides[get_current_user] = lambda: MockUser()
    app.dependency_overrides[get_session] = lambda: MockDB()
    yield
    app.dependency_overrides.clear()

def dummy_metric():
    return {
        "id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "name": "Dummy",
        "business_name": "Dummy",
        "description": "Desc",
        "expression": "1",
        "is_calculated": False,
        "aggregation_type": "SUM",
        "source_table_id": uuid.uuid4(),
        "source_column_id": uuid.uuid4(),
        "version": 1,
        "status": "approved",
        "owner": "test"
    }

@patch("app.api.semantic.MetricService")
def test_create_base_metric(mock_metric_service):
    mock_metric_service.create_metric.return_value = dummy_metric()
    res = client.post("/semantic/metrics", json={
        "name": "Gross_Revenue",
        "business_name": "Gross Revenue",
        "is_calculated": False,
        "aggregation_type": "SUM",
        "expression": "amount",
        "source_table_id": str(uuid.uuid4()),
        "source_column_id": str(uuid.uuid4())
    })
    assert res.status_code == 200

@patch("app.api.semantic.MetricService")
def test_get_metrics(mock_metric_service):
    mock_metric_service.list_metrics.return_value = [dummy_metric()]
    res = client.get("/semantic/metrics")
    assert res.status_code == 200

@patch("app.api.semantic.MetricService")
def test_get_metric(mock_metric_service):
    mock_metric_service.get_metric.return_value = dummy_metric()
    res = client.get(f"/semantic/metrics/{uuid.uuid4()}")
    assert res.status_code == 200

@patch("app.api.semantic.MetricService")
def test_update_metric(mock_metric_service):
    mock_metric_service.update_metric.return_value = dummy_metric()
    res = client.put(f"/semantic/metrics/{uuid.uuid4()}", json={
        "name": "Gross_Revenue_Updated",
        "business_name": "Gross Revenue",
        "expression": "amount_2",
        "is_calculated": False,
        "aggregation_type": "SUM"
    })
    assert res.status_code == 200

@patch("app.api.semantic.MetricService")
def test_delete_metric(mock_metric_service):
    mock_metric_service.delete_metric.return_value = True
    res = client.delete(f"/semantic/metrics/{uuid.uuid4()}")
    assert res.status_code == 200

@patch("app.api.semantic.MetricService")
def test_get_versions(mock_metric_service):
    mock_metric_service.get_versions.return_value = [{
        "id": uuid.uuid4(),
        "metric_id": uuid.uuid4(),
        "version": 1,
        "snapshot": {},
        "created_by": "test",
        "change_reason": "none"
    }]
    res = client.get(f"/semantic/metrics/{uuid.uuid4()}/versions")
    assert res.status_code == 200

@patch("app.api.semantic.MetricService")
def test_rollback_metric(mock_metric_service):
    mock_metric_service.rollback_metric.return_value = dummy_metric()
    res = client.post(f"/semantic/metrics/{uuid.uuid4()}/rollback?version=1")
    assert res.status_code == 200

@patch("app.api.semantic.GlossaryService")
def test_create_glossary(mock_glossary_service):
    mock_glossary_service.create_term.return_value = {
        "id": uuid.uuid4(),
        "term": "MAU",
        "business_definition": "Monthly Active Users",
        "status": "draft",
        "version": 1
    }
    res = client.post("/semantic/glossary", json={
        "term": "MAU",
        "business_definition": "Monthly Active Users"
    })
    assert res.status_code == 200
    
@patch("app.api.semantic.DimensionService")
def test_create_dimension(mock_dim_service):
    mock_dim_service.create_dimension.return_value = {
        "id": uuid.uuid4(),
        "business_name": "Customer Segment",
        "data_type": "TEXT",
        "is_time_dimension": False,
        "time_granularity": "NONE",
        "visibility": "visible",
        "status": "draft",
        "version": 1
    }
    res = client.post("/semantic/dimensions", json={
        "business_name": "Customer Segment",
        "data_type": "TEXT"
    })
    assert res.status_code == 200

@patch("app.api.semantic.JoinService")
def test_create_join(mock_join_service):
    mock_join_service.create_join.return_value = {
        "id": uuid.uuid4(),
        "left_table_id": uuid.uuid4(),
        "right_table_id": uuid.uuid4(),
        "join_condition": "A = B",
        "join_type": "LEFT",
        "cardinality": "many_to_one",
        "confidence": 1.0,
        "status": "draft",
        "version": 1
    }
    res = client.post("/semantic/joins", json={
        "left_table_id": str(uuid.uuid4()),
        "right_table_id": str(uuid.uuid4()),
        "join_condition": "A = B"
    })
    assert res.status_code == 200

@patch("app.api.semantic.SynonymService")
def test_synonyms(mock_syn_service):
    class MockSyn:
        id = uuid.uuid4()
        synonym = "Sales"
    mock_syn_service.add_synonym.return_value = MockSyn()
    mock_syn_service.resolve_synonym.return_value = {"resolved": True, "target_type": "METRIC", "target_id": uuid.uuid4()}
    
    res = client.post("/semantic/synonyms", json={
        "synonym_term": "Sales",
        "target_type": "metric",
        "target_id": str(uuid.uuid4())
    })
    assert res.status_code == 200
    
    res = client.get("/semantic/synonyms/resolve?term=Sales")
    assert res.status_code == 200
