"""Unit tests for ExecutorService customer database execution (Gap 2)."""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from app.engine.compiler_service import CompiledQuery
from app.engine.executor_service import ExecutorResult, ExecutorService
from app.models import DataSource


def test_executor_uses_build_engine_and_disposes():
    source = MagicMock(spec=DataSource)
    source.id = uuid.uuid4()
    source.name = "customer_sales_db"

    compiled = CompiledQuery(
        sql="SELECT total_sales FROM sales_summary WHERE tenant_id = :t_id",
        params={"t_id": "00000000-0000-0000-0000-000000000001"}
    )

    mock_engine = MagicMock()
    mock_connection = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_connection

    mock_result = MagicMock()
    mock_result.keys.return_value = ["total_sales"]
    
    mock_row = MagicMock()
    mock_row._mapping = {"total_sales": 50000.0}
    mock_result.fetchall.return_value = [mock_row]

    mock_connection.execute.return_value = mock_result

    with patch("app.engine.executor_service.build_engine", return_value=mock_engine) as mock_build_engine:
        res = ExecutorService.execute(source, compiled)

        mock_build_engine.assert_called_once_with(source)
        assert mock_engine.connect.called
        assert mock_engine.dispose.called
        assert res.columns == ["total_sales"]
        assert res.rows == [{"total_sales": 50000.0}]


def test_executor_disposes_engine_on_exception():
    source = MagicMock(spec=DataSource)
    source.id = uuid.uuid4()
    source.name = "customer_sales_db"

    compiled = CompiledQuery(sql="SELECT * FROM broken_table", params={})

    mock_engine = MagicMock()
    mock_connection = MagicMock()
    mock_connection.execute.side_effect = RuntimeError("Database connection lost")
    mock_engine.connect.return_value.__enter__.return_value = mock_connection

    with patch("app.engine.executor_service.build_engine", return_value=mock_engine):
        with pytest.raises(RuntimeError, match="Database connection lost"):
            ExecutorService.execute(source, compiled)

        assert mock_engine.dispose.called
