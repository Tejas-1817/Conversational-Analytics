"""Unit tests for schema snapshot export (Gap 1)."""
import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock

from app.ingestion.schema_export import export_schema_snapshot
from app.models import ColumnMeta, DataSource, MetadataVersion, TableMeta


def test_export_schema_snapshot_masks_sample_values(tmp_path, monkeypatch):
    monkeypatch.setattr("app.ingestion.schema_export.get_settings", lambda: MagicMock(schema_snapshot_dir=str(tmp_path)))
    
    tenant_id = uuid.uuid4()
    source_id = uuid.uuid4()
    
    source = MagicMock(spec=DataSource)
    source.id = source_id
    source.tenant_id = tenant_id
    source.name = "test_db"
    
    version = MagicMock(spec=MetadataVersion)
    version.version_number = 1
    
    table = MagicMock(spec=TableMeta)
    table.id = uuid.uuid4()
    table.schema_name = "public"
    table.table_name = "users"
    table.business_name = "Users"
    table.description = "User accounts"
    
    col_email = MagicMock(spec=ColumnMeta)
    col_email.id = uuid.uuid4()
    col_email.column_name = "email"
    col_email.data_type = "VARCHAR(255)"
    col_email.is_nullable = False
    col_email.is_primary_key = False
    col_email.role = "attribute"
    col_email.profile = {"sample_values": ["test@example.com", "user@test.org"]}

    col_name = MagicMock(spec=ColumnMeta)
    col_name.id = uuid.uuid4()
    col_name.column_name = "user_name"
    col_name.data_type = "VARCHAR(100)"
    col_name.is_nullable = True
    col_name.is_primary_key = False
    col_name.role = "dimension"
    col_name.profile = {"sample_values": ["John Doe"]}
    
    session = MagicMock()
    
    # Mock query returns for tables, columns, relationships
    def mock_query(model):
        query_mock = MagicMock()
        if model == TableMeta:
            query_mock.filter_by.return_value.all.return_value = [table]
        elif model == ColumnMeta:
            query_mock.filter_by.return_value.all.return_value = [col_email, col_name]
        else:
            query_mock.join.return_value.filter.return_value.all.return_value = []
        return query_mock
        
    session.query.side_effect = mock_query

    result = export_schema_snapshot(session, source, version)
    
    assert result["status"] == "succeeded"
    expected_file = tmp_path / str(tenant_id) / str(source_id) / "v1.json"
    assert expected_file.exists()
    
    content = json.loads(expected_file.read_text(encoding="utf-8"))
    assert content["version_number"] == 1
    assert len(content["tables"]) == 1
    cols = content["tables"][0]["columns"]
    
    # Verify sensitive column 'email' samples are masked
    email_col = next(c for c in cols if c["column_name"] == "email")
    assert email_col["sample_values"] == ["<masked: sensitive column>"]


def test_export_schema_snapshot_version_increment(tmp_path, monkeypatch):
    monkeypatch.setattr("app.ingestion.schema_export.get_settings", lambda: MagicMock(schema_snapshot_dir=str(tmp_path)))

    tenant_id = uuid.uuid4()
    source_id = uuid.uuid4()
    
    source = MagicMock(spec=DataSource)
    source.id = source_id
    source.tenant_id = tenant_id
    source.name = "test_db"
    
    session = MagicMock()
    session.query.return_value.filter_by.return_value.all.return_value = []

    version1 = MagicMock(spec=MetadataVersion)
    version1.version_number = 1

    version2 = MagicMock(spec=MetadataVersion)
    version2.version_number = 2

    export_schema_snapshot(session, source, version1)
    export_schema_snapshot(session, source, version2)

    v1_file = tmp_path / str(tenant_id) / str(source_id) / "v1.json"
    v2_file = tmp_path / str(tenant_id) / str(source_id) / "v2.json"

    assert v1_file.exists()
    assert v2_file.exists()
