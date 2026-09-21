"""Test suite for MySQL and MSSQL support alongside PostgreSQL."""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.engine import URL

from app.chat_sql.prompt_builder import PromptBuilder
from app.chat_sql.sql_validator import SQLValidator
from app.connectors.factory import verify_read_only


def test_prompt_builder_dialects():
    question = "How many orders were placed each month?"
    schema_text = "Table: orders, Columns: order_id, placed_at"

    # PostgreSQL dialect test
    pg_prompt = PromptBuilder.build_prompt(
        question=question,
        schema_text=schema_text,
        dialect="postgres"
    )
    assert "PostgreSQL" in pg_prompt
    assert "DATE_TRUNC('month'" in pg_prompt
    assert "LIMIT" in pg_prompt

    # MySQL dialect test
    mysql_prompt = PromptBuilder.build_prompt(
        question=question,
        schema_text=schema_text,
        dialect="mysql"
    )
    assert "MySQL" in mysql_prompt
    assert "DATE_FORMAT" in mysql_prompt
    assert "LIMIT" in mysql_prompt

    # MSSQL dialect test
    mssql_prompt = PromptBuilder.build_prompt(
        question=question,
        schema_text=schema_text,
        dialect="mssql"
    )
    assert "Microsoft SQL Server" in mssql_prompt
    assert "DATETRUNC(month" in mssql_prompt
    assert "NEVER use LIMIT keyword in MSSQL" in mssql_prompt


def test_sql_validator_dialects():
    catalog = {
        "orders": {"order_id", "placed_at", "total_amount"},
        "dbo.orders": {"order_id", "placed_at", "total_amount"},
        "public.orders": {"order_id", "placed_at", "total_amount"},
    }

    # Postgres valid query
    pg_sql = "SELECT DATE_TRUNC('month', placed_at) AS m, COUNT(order_id) AS cnt FROM public.orders GROUP BY DATE_TRUNC('month', placed_at)"
    assert SQLValidator.validate_sql(pg_sql, catalog=catalog, dialect="postgres") != "UNANSWERABLE"

    # MySQL valid query with DATE_FORMAT (which postgres validator would reject)
    mysql_sql = "SELECT DATE_FORMAT(placed_at, '%Y-%m-01') AS m, COUNT(order_id) AS cnt FROM orders GROUP BY DATE_FORMAT(placed_at, '%Y-%m-01') LIMIT 10"
    mysql_res = SQLValidator.validate_sql(mysql_sql, catalog=catalog, dialect="mysql")
    assert mysql_res != "UNANSWERABLE"

    # MSSQL valid query with TOP and brackets
    mssql_sql = "SELECT TOP (10) order_id, total_amount FROM [dbo].[orders]"
    mssql_res = SQLValidator.validate_sql(mssql_sql, catalog=catalog, dialect="mssql")
    assert mssql_res != "UNANSWERABLE"

def test_sql_validator_accepts_cte_and_derived_table_alias():
    sql = """
    WITH monthly_sales AS (
        SELECT
            d.calendar_year,
            d.month_number,
            SUM(i.net_amount) AS monthly_revenue
        FROM fact_sales AS s
        JOIN fact_sales_item AS i
            ON i.sale_id = s.sale_id
        JOIN dim_date AS d
            ON d.date_key = s.date_key
        GROUP BY
            d.calendar_year,
            d.month_number
    )
    SELECT
        ms.month_number,
        ms.monthly_revenue
    FROM monthly_sales AS ms;
    """

    catalog = {
        "fact_sales": {
            "sale_id",
            "date_key",
        },
        "fact_sales_item": {
            "sale_id",
            "net_amount",
        },
        "dim_date": {
            "date_key",
            "calendar_year",
            "month_number",
        },
    }

    result = SQLValidator.validate_sql(
        sql,
        catalog=catalog,
        dialect="mssql",
    )

    assert result != "UNANSWERABLE"

    # Destructive queries blocked across all dialects
    bad_sql = "DROP TABLE orders;"
    assert SQLValidator.validate_sql(bad_sql, catalog=catalog, dialect="mysql") == "UNANSWERABLE"
    assert SQLValidator.validate_sql(bad_sql, catalog=catalog, dialect="mssql") == "UNANSWERABLE"


def test_verify_read_only_mysql():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    # Read-only grants
    mock_conn.execute.return_value = [("GRANT SELECT ON `analytics`.* TO 'reader'@'%'",)]
    # Should not raise
    verify_read_only(mock_engine, "mysql")

    # Writable grants
    mock_conn.execute.return_value = [("GRANT SELECT, INSERT, UPDATE ON `analytics`.* TO 'writer'@'%'",)]
    with pytest.raises(PermissionError):
        verify_read_only(mock_engine, "mysql")


def test_verify_read_only_mssql():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    # Read-only user (0 write permissions)
    mock_conn.execute.return_value.scalar_one.return_value = 0
    verify_read_only(mock_engine, "mssql")

    # User with write permissions
    mock_conn.execute.return_value.scalar_one.return_value = 2
    with pytest.raises(PermissionError):
        verify_read_only(mock_engine, "mssql")


if __name__ == "__main__":
    test_prompt_builder_dialects()
    test_sql_validator_dialects()
    test_verify_read_only_mysql()
    test_verify_read_only_mssql()
    print("All multi-database connectivity tests passed successfully!")
