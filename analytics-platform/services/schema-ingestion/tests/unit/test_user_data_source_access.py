"""Unit tests for User Data Source Access Control (DAC)."""
import uuid
import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock

from app.api.deps import verify_user_has_source_access
from app.models import User, UserDataSourceAccess
from app.schemas import (
    UserDataSourceAccessUpdate,
    UserDataSourceItemOut,
    SourceUserAccessItemOut,
    SourceUserAccessUpdate,
)


class TestUserDataSourceAccessControl:
    """Tests for granular user-level data source access checking and schemas."""

    def test_admin_bypasses_data_source_access_check(self):
        """ADMIN users must always bypass data source access verification."""
        tenant_id = uuid.uuid4()
        source_id = uuid.uuid4()
        admin_user = User(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            email="admin@example.com",
            role="ADMIN",
            is_active=True,
        )

        mock_session = MagicMock()
        # Should not raise any exception, and should not even query the session
        verify_user_has_source_access(mock_session, admin_user, source_id)
        mock_session.scalar.assert_not_called()

    def test_analyst_with_grant_passes_access_check(self):
        """Non-admin user who has been granted access in the DB passes verification."""
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        source_id = uuid.uuid4()

        analyst_user = User(
            id=user_id,
            tenant_id=tenant_id,
            email="analyst@example.com",
            role="ANALYST",
            is_active=True,
        )

        mock_grant = UserDataSourceAccess(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            source_id=source_id,
            granted_by="admin@example.com",
        )

        mock_session = MagicMock()
        mock_session.scalar.return_value = mock_grant

        # Should execute cleanly
        verify_user_has_source_access(mock_session, analyst_user, source_id)
        mock_session.scalar.assert_called_once()

    def test_analyst_without_grant_raises_403(self):
        """Non-admin user without a grant must receive HTTP 403 Forbidden."""
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        source_id = uuid.uuid4()

        viewer_user = User(
            id=user_id,
            tenant_id=tenant_id,
            email="viewer@example.com",
            role="VIEWER",
            is_active=True,
        )

        mock_session = MagicMock()
        mock_session.scalar.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            verify_user_has_source_access(mock_session, viewer_user, source_id)

        assert exc_info.value.status_code == 403
        assert "permission to access this data source" in exc_info.value.detail

    def test_user_data_source_access_schemas(self):
        """Verify serialization and validation of Pydantic models."""
        source_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # Update schema
        update_schema = UserDataSourceAccessUpdate(source_ids=[source_id])
        assert update_schema.source_ids == [source_id]

        # User data source item out
        item_out = UserDataSourceItemOut(
            source_id=source_id,
            name="Main PostgreSQL",
            type="postgres",
            database_name="analytics",
            is_granted=True,
        )
        assert item_out.is_granted is True
        assert item_out.name == "Main PostgreSQL"

        # Source user access schemas
        source_user_out = SourceUserAccessItemOut(
            user_id=user_id,
            email="analyst@test.com",
            role="ANALYST",
            is_granted=False,
        )
        assert source_user_out.is_granted is False
        assert source_user_out.email == "analyst@test.com"

        source_user_update = SourceUserAccessUpdate(user_ids=[user_id])
        assert source_user_update.user_ids == [user_id]

    def test_admin_bypasses_domain_access_check(self):
        """ADMIN users bypass domain access checks directly."""
        from app.api.deps import verify_user_has_domain_access
        admin_user = User(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            email="admin@example.com",
            role="ADMIN",
            is_active=True,
        )
        mock_domain = MagicMock()
        mock_domain.id = uuid.uuid4()
        mock_domain.source_id = uuid.uuid4()
        mock_session = MagicMock()

        # Should not raise exception
        verify_user_has_domain_access(mock_session, admin_user, mock_domain)
        mock_session.scalar.assert_not_called()

    def test_non_admin_with_granted_source_passes_domain_check(self):
        """Non-admin user with granted source access can access the domain."""
        from app.api.deps import verify_user_has_domain_access
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        source_id = uuid.uuid4()

        analyst = User(
            id=user_id,
            tenant_id=tenant_id,
            email="analyst@example.com",
            role="ANALYST",
            is_active=True,
        )
        mock_domain = MagicMock()
        mock_domain.id = uuid.uuid4()
        mock_domain.source_id = source_id

        mock_grant = UserDataSourceAccess(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            source_id=source_id,
            granted_by="admin@example.com",
        )

        mock_session = MagicMock()
        mock_session.scalar.return_value = mock_grant

        # Should pass without error
        verify_user_has_domain_access(mock_session, analyst, mock_domain)
        mock_session.scalar.assert_called_once()

    def test_non_admin_without_granted_source_raises_403_for_domain(self):
        """Non-admin user without granted source access receives 403 Forbidden for the domain."""
        from app.api.deps import verify_user_has_domain_access
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        source_id = uuid.uuid4()

        analyst = User(
            id=user_id,
            tenant_id=tenant_id,
            email="analyst@example.com",
            role="ANALYST",
            is_active=True,
        )
        mock_domain = MagicMock()
        mock_domain.id = uuid.uuid4()
        mock_domain.source_id = source_id

        mock_session = MagicMock()
        mock_session.scalar.return_value = None  # No access grant

        with pytest.raises(HTTPException) as exc_info:
            verify_user_has_domain_access(mock_session, analyst, mock_domain)

        assert exc_info.value.status_code == 403

    def test_non_admin_with_other_source_grant_denied_for_unrelated_domain(self):
        """User with grant for Source A cannot access domain for Source B."""
        from app.api.deps import verify_user_has_domain_access
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        source_a_id = uuid.uuid4()
        source_b_id = uuid.uuid4()

        analyst = User(
            id=user_id,
            tenant_id=tenant_id,
            email="analyst@example.com",
            role="ANALYST",
            is_active=True,
        )
        mock_domain = MagicMock()
        mock_domain.id = uuid.uuid4()
        mock_domain.source_id = source_b_id

        mock_session = MagicMock()
        # First call has_any_grant -> returns True (user has some grant)
        # Second call verify_user_has_source_access -> returns None (user does not have grant for source_b)
        mock_session.scalar.side_effect = [uuid.uuid4(), None]

        with pytest.raises(HTTPException) as exc_info:
            verify_user_has_domain_access(mock_session, analyst, mock_domain)

        assert exc_info.value.status_code == 403
        assert "permission to access the data source for this domain" in exc_info.value.detail

    def test_non_admin_domain_table_source_without_grant_raises_403(self):
        """If domain.source_id is None, checks table sources and denies if user lacks access."""
        from app.api.deps import verify_user_has_domain_access
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        table_source_id = uuid.uuid4()

        analyst = User(
            id=user_id,
            tenant_id=tenant_id,
            email="analyst@example.com",
            role="ANALYST",
            is_active=True,
        )
        mock_domain = MagicMock()
        mock_domain.id = uuid.uuid4()
        mock_domain.source_id = None

        mock_session = MagicMock()
        # has_any_grant -> returns True
        # table query -> returns table_source_id
        # verify_user_has_source_access -> returns None (no grant)
        mock_session.scalar.side_effect = [uuid.uuid4(), None]

        mock_query = MagicMock()
        mock_query.join.return_value.filter.return_value.distinct.return_value.all.return_value = [
            (table_source_id,)
        ]
        mock_session.query.return_value = mock_query

        with pytest.raises(HTTPException) as exc_info:
            verify_user_has_domain_access(mock_session, analyst, mock_domain)

        assert exc_info.value.status_code == 403
        assert "permission to access the data source for this domain" in exc_info.value.detail

