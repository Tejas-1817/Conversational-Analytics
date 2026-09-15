"""Unit tests for Excel connector and SQLite read-only enforcement."""
import sqlite3
import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.connectors.factory import build_engine, verify_read_only
from app.models import DataSource


def test_excel_build_engine_read_only_enforcement(tmp_path):
    """Confirm that an engine created for type='excel' rejects any INSERT/UPDATE/DELETE/CREATE writes."""
    db_file = tmp_path / "test_ro.db"
    
    # Create the database with an initial table
    with sqlite3.connect(str(db_file)) as conn:
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);")
        conn.execute("INSERT INTO users (id, name) VALUES (1, 'Alice');")
        conn.commit()

    source = DataSource(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        name="Excel Test",
        type="excel",
        file_path=str(db_file),
        created_by="test@example.com",
        updated_by="test@example.com"
    )

    engine = build_engine(source)

    # 1. Reading should work cleanly
    with engine.connect() as conn:
        res = conn.execute(text("SELECT name FROM users WHERE id = 1;")).scalar()
        assert res == "Alice"

    # 2. Writing (INSERT) must raise OperationalError (attempt to write a readonly database)
    with pytest.raises(OperationalError) as exc_info:
        with engine.connect() as conn:
            conn.execute(text("INSERT INTO users (id, name) VALUES (2, 'Bob');"))
            conn.commit()

    assert "readonly" in str(exc_info.value).lower()

    # 3. Writing (UPDATE) must raise OperationalError
    with pytest.raises(OperationalError):
        with engine.connect() as conn:
            conn.execute(text("UPDATE users SET name = 'Charlie' WHERE id = 1;"))
            conn.commit()

    # 4. Writing (DELETE) must raise OperationalError
    with pytest.raises(OperationalError):
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM users WHERE id = 1;"))
            conn.commit()


def test_excel_verify_read_only():
    """Verify verify_read_only returns cleanly for excel sources."""
    # Should not raise any exception
    verify_read_only(None, "excel")
