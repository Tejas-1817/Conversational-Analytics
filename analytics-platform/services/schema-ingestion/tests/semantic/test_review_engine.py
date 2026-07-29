import uuid
import pytest
from unittest.mock import MagicMock
from app.models import SemanticMetric, SemanticModel
from app.semantic.review_service import SemanticReviewService
from app.semantic.feedback_service import FeedbackService
from app.semantic.audit_service import AuditService
from app.semantic.version_service import VersionService
from fastapi import HTTPException

@pytest.fixture
def mock_db():
    session = MagicMock()
    return session

@pytest.fixture
def sample_metric():
    metric = SemanticMetric(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        semantic_model_id=uuid.uuid4(),
        name="Total Revenue",
        review_status="REVIEW_REQUIRED",
        version=1
    )
    return metric

@pytest.fixture
def sample_model():
    model = SemanticModel(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        semantic_version=1,
        is_active=False
    )
    return model

def test_approve_object(mock_db, sample_metric):
    mock_db.query().filter().first.return_value = sample_metric
    
    obj = SemanticReviewService.approve_object(
        db=mock_db,
        tenant_id=sample_metric.tenant_id,
        object_type="metric",
        object_id=sample_metric.id,
        actor="admin@test.com",
        reason="Looks good"
    )
    
    assert obj.review_status == "ACTIVE"
    mock_db.add.assert_called()  # Feedback and Audit
    mock_db.flush.assert_called()

def test_reject_object(mock_db, sample_metric):
    mock_db.query().filter().first.return_value = sample_metric
    
    obj = SemanticReviewService.reject_object(
        db=mock_db,
        tenant_id=sample_metric.tenant_id,
        object_type="metric",
        object_id=sample_metric.id,
        actor="admin@test.com",
        reason="Incorrect aggregation"
    )
    
    assert obj.review_status == "ARCHIVED"
    mock_db.add.assert_called()
    mock_db.flush.assert_called()

def test_update_object(mock_db, sample_metric):
    mock_db.query().filter().first.return_value = sample_metric
    
    obj = SemanticReviewService.update_object(
        db=mock_db,
        tenant_id=sample_metric.tenant_id,
        object_type="metric",
        object_id=sample_metric.id,
        updates={"name": "Total Sales Revenue"},
        actor="admin@test.com",
        reason="Better naming"
    )
    
    assert obj.name == "Total Sales Revenue"
    assert obj.version == 2
    assert obj.review_status == "ACTIVE"
    # snapshot_metric calls db.add for MetricVersion
    # feedback calls db.add
    # audit calls db.add
    assert mock_db.add.call_count == 3
    mock_db.flush.assert_called()

def test_rollback_semantic_model(mock_db, sample_model):
    mock_db.query().filter().first.side_effect = [sample_model, None]
    
    model = VersionService.rollback_semantic_model(
        db=mock_db,
        tenant_id=sample_model.tenant_id,
        source_id=sample_model.source_id,
        target_version=1,
        actor="admin@test.com"
    )
    
    assert model.id == sample_model.id
    mock_db.add.assert_called() # Audit log
