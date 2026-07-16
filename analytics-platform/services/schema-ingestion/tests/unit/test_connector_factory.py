"""Unit tests for connectors/factory.py.

Rules from testing.md:
- No network, no real DB — all engines are mocked.
- Test the guardrails hardest: write-privilege rejection is a security invariant.
- Confirm that a user WITH write privileges is REJECTED at registration time (not just
  "intended" to be — actually simulate the rejection path and assert PermissionError).
- Confirm retry-with-backoff fires on transient OperationalErrors.
"""
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from app.connectors.factory import (
    _RETRY_BASE_DELAY_S,
    MAX_CONNECT_RETRIES,
    _build_engine_with_retry,
    verify_read_only,
)

# ---------------------------------------------------------------------------
# Tests: verify_read_only — Postgres
# ---------------------------------------------------------------------------

class TestVerifyReadOnlyPostgres:
    def _make_engine(self, writable_table_count: int) -> MagicMock:
        engine = MagicMock()
        conn_ctx = MagicMock()
        conn_ctx.__enter__ = MagicMock(return_value=conn_ctx)
        conn_ctx.__exit__ = MagicMock(return_value=False)
        conn_ctx.execute.return_value.scalar_one.return_value = writable_table_count
        engine.connect.return_value = conn_ctx
        return engine

    def test_user_with_write_privileges_is_rejected(self):
        """A user that has write privileges on even one table must raise PermissionError.

        This is a hard security invariant — NOT just intended behaviour.
        """
        engine = self._make_engine(writable_table_count=3)
        with pytest.raises(PermissionError, match="write privileges"):
            verify_read_only(engine, "postgres")

    def test_user_with_no_write_privileges_is_accepted(self):
        """A user with zero writable tables must NOT raise."""
        engine = self._make_engine(writable_table_count=0)
        verify_read_only(engine, "postgres")  # must not raise

    def test_writable_table_count_of_one_is_rejected(self):
        """Even a single writable table is enough to block registration."""
        engine = self._make_engine(writable_table_count=1)
        with pytest.raises(PermissionError):
            verify_read_only(engine, "postgres")

    def test_error_message_includes_table_count(self):
        """The PermissionError must tell the operator how many tables are writable."""
        engine = self._make_engine(writable_table_count=7)
        with pytest.raises(PermissionError, match="7 table"):
            verify_read_only(engine, "postgres")


# ---------------------------------------------------------------------------
# Tests: verify_read_only — MySQL
# ---------------------------------------------------------------------------

class TestVerifyReadOnlyMySQL:
    def _make_mysql_engine(self, grants: list[str]) -> MagicMock:
        engine = MagicMock()
        conn_ctx = MagicMock()
        conn_ctx.__enter__ = MagicMock(return_value=conn_ctx)
        conn_ctx.__exit__ = MagicMock(return_value=False)
        conn_ctx.execute.return_value = [(g,) for g in grants]
        engine.connect.return_value = conn_ctx
        return engine

    def test_mysql_user_with_insert_grant_is_rejected(self):
        grants = ["GRANT SELECT, INSERT ON `shop`.* TO 'user'@'%'"]
        engine = self._make_mysql_engine(grants)
        with pytest.raises(PermissionError, match="write privileges"):
            verify_read_only(engine, "mysql")

    def test_mysql_user_with_all_privileges_is_rejected(self):
        grants = ["GRANT ALL PRIVILEGES ON *.* TO 'root'@'%'"]
        engine = self._make_mysql_engine(grants)
        with pytest.raises(PermissionError):
            verify_read_only(engine, "mysql")

    def test_mysql_select_only_user_is_accepted(self):
        grants = ["GRANT SELECT ON `shop`.* TO 'reader'@'%'"]
        engine = self._make_mysql_engine(grants)
        verify_read_only(engine, "mysql")  # must not raise


# ---------------------------------------------------------------------------
# Tests: retry-with-backoff
# ---------------------------------------------------------------------------

class TestBuildEngineWithRetry:
    @patch("app.connectors.factory.time.sleep")
    @patch("app.connectors.factory.create_engine")
    def test_succeeds_on_first_attempt_without_sleeping(self, mock_create_engine, mock_sleep):
        """When the first connection succeeds there must be zero sleeps."""
        engine = MagicMock()
        conn_ctx = MagicMock()
        conn_ctx.__enter__ = MagicMock(return_value=conn_ctx)
        conn_ctx.__exit__ = MagicMock(return_value=False)
        engine.connect.return_value = conn_ctx
        mock_create_engine.return_value = engine

        result = _build_engine_with_retry(MagicMock(), {}, {})
        assert result is engine
        mock_sleep.assert_not_called()

    @patch("app.connectors.factory.time.sleep")
    @patch("app.connectors.factory.create_engine")
    def test_retries_on_transient_operational_error_and_eventually_succeeds(
        self, mock_create_engine, mock_sleep
    ):
        """On transient OperationalError, the factory retries up to MAX_CONNECT_RETRIES
        times with exponential back-off, then returns the engine on success."""
        good_engine = MagicMock()
        conn_ctx = MagicMock()
        conn_ctx.__enter__ = MagicMock(return_value=conn_ctx)
        conn_ctx.__exit__ = MagicMock(return_value=False)
        good_engine.connect.return_value = conn_ctx

        # Fail twice, then succeed
        failing_engine = MagicMock()
        failing_engine.connect.side_effect = OperationalError("timeout", None, None)

        mock_create_engine.side_effect = [failing_engine, failing_engine, good_engine]

        result = _build_engine_with_retry(MagicMock(), {}, {})
        assert result is good_engine
        assert mock_sleep.call_count == 2  # slept after attempt 1 and 2

        # Verify backoff doubles: first sleep = base, second = base * 2
        sleep_args = [c.args[0] for c in mock_sleep.call_args_list]
        assert sleep_args[0] == pytest.approx(_RETRY_BASE_DELAY_S)
        assert sleep_args[1] == pytest.approx(_RETRY_BASE_DELAY_S * 2)

    @patch("app.connectors.factory.time.sleep")
    @patch("app.connectors.factory.create_engine")
    def test_raises_after_all_retries_exhausted(self, mock_create_engine, mock_sleep):
        """When all MAX_CONNECT_RETRIES attempts fail, the last OperationalError is re-raised."""
        bad_engine = MagicMock()
        bad_engine.connect.side_effect = OperationalError("connection refused", None, None)
        mock_create_engine.return_value = bad_engine

        with pytest.raises(OperationalError):
            _build_engine_with_retry(MagicMock(), {}, {})

        # Slept MAX_CONNECT_RETRIES - 1 times (no sleep after the last attempt)
        assert mock_sleep.call_count == MAX_CONNECT_RETRIES - 1

    @patch("app.connectors.factory.time.sleep")
    @patch("app.connectors.factory.create_engine")
    def test_non_operational_error_surfaces_immediately_without_retry(
        self, mock_create_engine, mock_sleep
    ):
        """Non-OperationalError exceptions (e.g. auth errors as ProgrammingError) must
        bubble up immediately — no retry loop, no sleep."""
        bad_engine = MagicMock()
        bad_engine.connect.side_effect = ValueError("bad credentials format")
        mock_create_engine.return_value = bad_engine

        with pytest.raises(ValueError, match="bad credentials"):
            _build_engine_with_retry(MagicMock(), {}, {})

        mock_sleep.assert_not_called()
        # create_engine was called only once
        assert mock_create_engine.call_count == 1
