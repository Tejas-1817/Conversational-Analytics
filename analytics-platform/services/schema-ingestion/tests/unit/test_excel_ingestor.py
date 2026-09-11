"""Unit tests for Excel ingestion and SQLite materialization."""
import sqlite3
import pandas as pd
import pytest
from app.ingestion.excel_ingestor import (
    sanitize_identifier,
    sanitize_column_names,
    preview_excel_sheets,
    materialize_excel_to_sqlite,
)


def test_sanitize_identifier():
    assert sanitize_identifier("Orders & Transactions") == "orders_transactions"
    assert sanitize_identifier("123 Sales Data") == "sales_data"
    assert sanitize_identifier("Amount ($)") == "amount"
    assert sanitize_identifier("col.1") == "col_1"
    assert sanitize_identifier("___weird___name___") == "weird_name"
    assert sanitize_identifier("") == "unnamed_column"


def test_sanitize_column_names():
    raw_cols = ["ID", "Customer Name", "ID", "Amount ($)", "Amount ($)"]
    clean_cols = sanitize_column_names(raw_cols)
    assert clean_cols == ["id", "customer_name", "id_2", "amount", "amount_2"]


def test_materialize_multi_sheet_with_same_column_names(tmp_path):
    """Test (a): 2+ sheets sharing column names produce independent tables without interference."""
    excel_path = tmp_path / "multi_sheet.xlsx"
    sqlite_path = tmp_path / "materialized.db"

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        df_orders = pd.DataFrame({
            "id": [1, 2, 3],
            "date": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "amount": [100.5, 200.0, 350.75]
        })
        df_payments = pd.DataFrame({
            "id": [10, 20],
            "date": ["2026-01-05", "2026-01-06"],
            "amount": [50.0, 75.25],
            "method": ["credit_card", "upi"]
        })
        df_orders.to_excel(writer, sheet_name="Orders", index=False)
        df_payments.to_excel(writer, sheet_name="Payments", index=False)

    stats = materialize_excel_to_sqlite(excel_path, sqlite_path)

    assert stats["sheets_total"] == 2
    assert stats["sheets_ingested"] == 2
    assert stats["sheets_skipped"] == 0

    with sqlite3.connect(str(sqlite_path)) as conn:
        cursor = conn.cursor()
        tables = [row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")]
        assert "orders" in tables
        assert "payments" in tables

        orders_count = cursor.execute("SELECT COUNT(*) FROM orders;").fetchone()[0]
        payments_count = cursor.execute("SELECT COUNT(*) FROM payments;").fetchone()[0]
        assert orders_count == 3
        assert payments_count == 2


def test_colliding_sheet_names_deduplication(tmp_path):
    """Test (b): Sanitization + dedup of colliding sheet names."""
    excel_path = tmp_path / "colliding_sheets.xlsx"
    sqlite_path = tmp_path / "materialized.db"

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        df1 = pd.DataFrame({"col_a": [1, 2]})
        df2 = pd.DataFrame({"col_b": [3, 4]})
        df1.to_excel(writer, sheet_name="Sales Data", index=False)
        df2.to_excel(writer, sheet_name="Sales-Data!", index=False)

    stats = materialize_excel_to_sqlite(excel_path, sqlite_path)

    assert stats["sheets_ingested"] == 2
    table_names = [t["table_name"] for t in stats["tables"]]
    assert table_names == ["sales_data", "sales_data_2"]

    with sqlite3.connect(str(sqlite_path)) as conn:
        cursor = conn.cursor()
        tables = [row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")]
        assert "sales_data" in tables
        assert "sales_data_2" in tables


def test_mixed_type_column_coerced_to_text(tmp_path):
    """Test (c): Mixed-type column is coerced to TEXT without data corruption."""
    excel_path = tmp_path / "mixed_types.xlsx"
    sqlite_path = tmp_path / "materialized.db"

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        df = pd.DataFrame({
            "mixed_col": [123, "ABC", 456.78, "XYZ", None]
        })
        df.to_excel(writer, sheet_name="MixedData", index=False)

    stats = materialize_excel_to_sqlite(excel_path, sqlite_path)
    assert stats["sheets_ingested"] == 1

    with sqlite3.connect(str(sqlite_path)) as conn:
        cursor = conn.cursor()
        rows = [row[0] for row in cursor.execute("SELECT mixed_col FROM mixeddata;")]
        assert rows == ["123", "ABC", "456.78", "XYZ", None]


def test_empty_sheet_skipped_reported_in_stats(tmp_path):
    """Test (d): Empty sheet is skipped and reported in stats, not turned into an empty table."""
    excel_path = tmp_path / "empty_sheet.xlsx"
    sqlite_path = tmp_path / "materialized.db"

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        df_valid = pd.DataFrame({"val": [10, 20]})
        df_empty = pd.DataFrame()
        df_valid.to_excel(writer, sheet_name="ValidSheet", index=False)
        df_empty.to_excel(writer, sheet_name="EmptySheet", index=False)

    stats = materialize_excel_to_sqlite(excel_path, sqlite_path)

    assert stats["sheets_total"] == 2
    assert stats["sheets_ingested"] == 1
    assert stats["sheets_skipped"] == 1
    assert any("EmptySheet" in w for w in stats["warnings"])

    with sqlite3.connect(str(sqlite_path)) as conn:
        cursor = conn.cursor()
        tables = [row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")]
        assert "validsheet" in tables
        assert "emptysheet" not in tables


def test_preview_excel_sheets(tmp_path):
    """Test previewing sheets without materialization."""
    excel_path = tmp_path / "preview.xlsx"

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        df = pd.DataFrame({
            "Product ID": [1, 2, 3],
            "Price": [19.99, 29.99, 49.99]
        })
        df.to_excel(writer, sheet_name="Products", index=False)

    preview = preview_excel_sheets(excel_path)
    assert len(preview["sheets"]) == 1
    sheet = preview["sheets"][0]
    assert sheet["sheet_name"] == "Products"
    assert sheet["suggested_table_name"] == "products"
    assert sheet["column_names"] == ["product_id", "price"]
    assert len(sheet["preview_rows"]) == 3
