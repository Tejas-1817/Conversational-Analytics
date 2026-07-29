import uuid
import pytest
from unittest.mock import MagicMock
from app.models import TableMeta, ColumnMeta
from app.schemas_semantic_ai import (
    AITableEnrichmentSchema, AIDimensionSchema, AIMeasureSchema, 
    AIKPISchema, AIGlossaryTermSchema, AISemanticRelationshipSchema
)
from app.semantic.validation_service import SemanticValidationService
from app.schemas_validation import ValidationStatus

@pytest.fixture
def mock_db_session():
    session = MagicMock()
    return session

@pytest.fixture
def sample_table():
    table = TableMeta(
        id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        table_name="orders",
        schema_name="public",
        columns=[
            ColumnMeta(id=uuid.uuid4(), column_name="id", data_type="integer"),
            ColumnMeta(id=uuid.uuid4(), column_name="user_id", data_type="integer"),
            ColumnMeta(id=uuid.uuid4(), column_name="amount", data_type="decimal"),
            ColumnMeta(id=uuid.uuid4(), column_name="created_at", data_type="timestamp"),
            ColumnMeta(id=uuid.uuid4(), column_name="status", data_type="varchar"),
        ]
    )
    return table

def test_validation_dimensions(sample_table, mock_db_session):
    enrichment = AITableEnrichmentSchema(
        business_description="Test",
        dimensions=[
            AIDimensionSchema(business_name="Status", description="Order Status", source_column_name="status", is_time_dimension=False),
            AIDimensionSchema(business_name="Order Date", description="Date created", source_column_name="created_at", is_time_dimension=True),
            AIDimensionSchema(business_name="Invalid Col", description="Missing col", source_column_name="missing_col", is_time_dimension=False)
        ],
        measures=[],
        confidence_score=0.9
    )
    
    enriched, report = SemanticValidationService.validate_table_enrichment(mock_db_session, sample_table, enrichment)
    
    # 3 dimensions: 2 valid, 1 invalid (missing column)
    assert report.total_objects == 3
    assert report.validated_objects == 2
    assert report.failed_validations == 1
    
    status_map = {r.object_name: r.status for r in report.results}
    assert status_map["Status"] == ValidationStatus.VALIDATED
    assert status_map["Order Date"] == ValidationStatus.VALIDATED
    assert status_map["Invalid Col"] == ValidationStatus.INSUFFICIENT_EVIDENCE


def test_validation_measures(sample_table, mock_db_session):
    enrichment = AITableEnrichmentSchema(
        business_description="Test",
        dimensions=[],
        measures=[
            AIMeasureSchema(business_name="Total Amount", description="Sum of amounts", source_column_name="amount", aggregation_type="SUM"),
            AIMeasureSchema(business_name="Invalid Agg", description="Avg of status string", source_column_name="status", aggregation_type="SUM"),
            AIMeasureSchema(business_name="Bad Col Measure", description="", source_column_name="nonexistent", aggregation_type="COUNT")
        ],
        confidence_score=0.9
    )
    
    enriched, report = SemanticValidationService.validate_table_enrichment(mock_db_session, sample_table, enrichment)
    
    status_map = {r.object_name: r.status for r in report.results}
    assert status_map["Total Amount"] == ValidationStatus.VALIDATED
    assert status_map["Invalid Agg"] == ValidationStatus.AMBIGUOUS  # Because SUM on varchar
    assert status_map["Bad Col Measure"] == ValidationStatus.INSUFFICIENT_EVIDENCE


def test_validation_relationships(sample_table, mock_db_session):
    # Mocking target table lookup
    target_table = TableMeta(id=uuid.uuid4(), source_id=sample_table.source_id, table_name="users")
    target_col = ColumnMeta(id=uuid.uuid4(), table_id=target_table.id, column_name="id", data_type="integer")
    
    def mock_query(model):
        query = MagicMock()
        if model == TableMeta:
            query.filter.return_value.first.return_value = target_table
        elif model == ColumnMeta:
            query.filter.return_value.first.return_value = target_col
        return query
        
    mock_db_session.query.side_effect = mock_query

    enrichment = AITableEnrichmentSchema(
        business_description="Test",
        dimensions=[],
        measures=[],
        relationships=[
            AISemanticRelationshipSchema(from_column_name="user_id", to_table_name="users", to_column_name="id", cardinality="many_to_one")
        ],
        confidence_score=0.9
    )
    
    enriched, report = SemanticValidationService.validate_table_enrichment(mock_db_session, sample_table, enrichment)
    
    assert report.validated_objects == 1
    assert report.results[0].status == ValidationStatus.VALIDATED
    
def test_validation_kpis(sample_table, mock_db_session):
    enrichment = AITableEnrichmentSchema(
        business_description="Test",
        dimensions=[],
        measures=[],
        kpis=[
            AIKPISchema(business_name="Valid KPI", description="", is_calculated=True, expression="SUM(amount) / COUNT(id)"),
            AIKPISchema(business_name="Invalid KPI", description="", is_calculated=True, expression="INVALID SYNTAX")
        ],
        confidence_score=0.9
    )
    
    enriched, report = SemanticValidationService.validate_table_enrichment(mock_db_session, sample_table, enrichment)
    
    status_map = {r.object_name: r.status for r in report.results}
    assert status_map["Valid KPI"] == ValidationStatus.VALIDATED
    assert status_map["Invalid KPI"] == ValidationStatus.INSUFFICIENT_EVIDENCE
