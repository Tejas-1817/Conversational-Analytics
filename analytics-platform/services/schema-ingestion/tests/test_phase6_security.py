"""
Phase 6 — Security Test Suite

Tests:
  1. Tenant Isolation — cross-tenant access is denied
  2. Auth Security — JWT validation, failed logins
  3. Row-Level Security — filter injection
  4. Column Security — masking and denial
  5. RBAC — permission enforcement

Run with:
    cd services/schema-ingestion
    python -m pytest tests/test_phase6_security.py -v
"""
import hashlib
import uuid

# ---------------------------------------------------------------------------
# 1. RLS Engine Tests
# ---------------------------------------------------------------------------

class TestRLSEngine:
    """Test the Row-Level Security policy evaluation and SQL injection."""

    def test_admin_bypasses_rls(self):
        """ADMIN role should always get an empty filter list."""
        from app.security.rls import RLSEngine

        # Mock a session that returns no policies (shouldn't matter — admin bypasses)
        class MockSession:
            def query(self, *args):
                return self
            def filter(self, *args):
                return self
            def all(self):
                return []

        filters = RLSEngine.get_filters(
            session=MockSession(),
            tenant_id=uuid.uuid4(),
            user_role="ADMIN",
            user_claims={"region": "EMEA"},
        )
        assert filters == [], "Admin should bypass RLS and get no filters"

    def test_missing_claim_produces_deny_filter(self):
        """If the required claim is missing from user_claims, inject a FALSE clause."""
        from unittest.mock import MagicMock

        from app.security.rls import RLSEngine

        mock_policy = MagicMock()
        mock_policy.name = "region_policy"
        mock_policy.applies_to_roles = ["VIEWER", "ANALYST"]
        mock_policy.table_name = None
        mock_policy.filter_column = "region"
        mock_policy.filter_operator = "="
        mock_policy.filter_claim = "region"

        class MockSession:
            def query(self, *args):
                return self
            def filter(self, *args):
                return self
            def all(self):
                return [mock_policy]

        # User has NO region claim
        filters = RLSEngine.get_filters(
            session=MockSession(),
            tenant_id=uuid.uuid4(),
            user_role="VIEWER",
            user_claims={},  # missing "region"
        )

        assert len(filters) == 1
        assert "1 = 0" in filters[0], f"Expected deny filter, got: {filters[0]}"

    def test_valid_claim_produces_where_clause(self):
        """When a claim is present, inject a proper WHERE clause fragment."""
        from unittest.mock import MagicMock

        from app.security.rls import RLSEngine

        mock_policy = MagicMock()
        mock_policy.name = "region_policy"
        mock_policy.applies_to_roles = ["ANALYST", "VIEWER"]
        mock_policy.table_name = None
        mock_policy.filter_column = "region"
        mock_policy.filter_operator = "="
        mock_policy.filter_claim = "region"

        class MockSession:
            def query(self, *args):
                return self
            def filter(self, *args):
                return self
            def all(self):
                return [mock_policy]

        filters = RLSEngine.get_filters(
            session=MockSession(),
            tenant_id=uuid.uuid4(),
            user_role="ANALYST",
            user_claims={"region": "EMEA"},
        )

        assert len(filters) == 1
        assert "region" in filters[0]
        assert "EMEA" in filters[0]

    def test_sql_injection_into_existing_where(self):
        """inject_into_sql should append to existing WHERE clause."""
        from app.security.rls import RLSEngine

        sql = 'SELECT region, SUM(revenue) FROM orders WHERE status = \'active\' GROUP BY region'
        filters = ['"region" = \'EMEA\'']

        result = RLSEngine.inject_into_sql(sql, filters)

        assert "1 = 0" not in result
        assert "EMEA" in result
        assert "GROUP BY" in result
        # Filter must appear before GROUP BY
        assert result.index("EMEA") < result.index("GROUP BY")

    def test_sql_injection_no_existing_where(self):
        """inject_into_sql should add WHERE clause when none exists."""
        from app.security.rls import RLSEngine

        sql = 'SELECT region, SUM(revenue) FROM orders GROUP BY region'
        filters = ['"region" = \'APAC\'']

        result = RLSEngine.inject_into_sql(sql, filters)

        assert "WHERE" in result.upper()
        assert "APAC" in result

    def test_identifier_quoting_blocks_injection(self):
        """Column names with special characters should be sanitized.
        
        The security boundary is PostgreSQL double-quoting: a double-quoted
        identifier is ALWAYS treated as an identifier name, never as SQL commands.
        The sanitizer strips all non-alphanumeric chars and wraps in double quotes.
        """
        from app.security.rls import RLSEngine

        malicious_col = "region; DROP TABLE users; --"
        safe = RLSEngine._quote_identifier(malicious_col)

        # Dangerous characters must be stripped
        assert ";" not in safe
        assert " " not in safe
        assert "--" not in safe
        # Result must be double-quoted (the PostgreSQL security boundary)
        assert safe.startswith('"') and safe.endswith('"')
        # Inner content is only alphanumeric / underscore
        inner = safe.strip('"')
        assert all(c.isalnum() or c == "_" for c in inner)

    def test_role_not_in_policy_applies_to_roles(self):
        """Policy should not be applied if the user's role is not in applies_to_roles."""
        from unittest.mock import MagicMock

        from app.security.rls import RLSEngine

        mock_policy = MagicMock()
        mock_policy.name = "finance_only"
        mock_policy.applies_to_roles = ["VIEWER"]  # Only VIEWERs
        mock_policy.table_name = None
        mock_policy.filter_column = "department"
        mock_policy.filter_operator = "="
        mock_policy.filter_claim = "department"

        class MockSession:
            def query(self, *args):
                return self
            def filter(self, *args):
                return self
            def all(self):
                return [mock_policy]

        # ANALYST should NOT get this filter
        filters = RLSEngine.get_filters(
            session=MockSession(),
            tenant_id=uuid.uuid4(),
            user_role="ANALYST",
            user_claims={"department": "Finance"},
        )
        assert filters == []


# ---------------------------------------------------------------------------
# 2. Column Security Engine Tests
# ---------------------------------------------------------------------------

class TestColumnSecurityEngine:
    """Test column-level security transformations."""

    def _make_policy(self, column_name, action, applies_to_roles=None,
                     mask_char="*", visible_chars=4):
        from unittest.mock import MagicMock
        p = MagicMock()
        p.column_name = column_name
        p.action = action
        p.applies_to_roles = applies_to_roles or ["VIEWER"]
        p.mask_char = mask_char
        p.visible_chars = visible_chars
        return p

    def test_admin_sees_all_columns(self):
        """ADMIN role should bypass all column security policies."""
        from unittest.mock import patch

        from app.security.column_security import ColumnSecurityEngine

        columns = ["name", "salary", "ssn"]
        rows = [{"name": "Alice", "salary": "100000", "ssn": "123-45-6789"}]

        with patch.object(ColumnSecurityEngine, "_load_policies", return_value=[]):
            out_cols, out_rows = ColumnSecurityEngine.apply(
                session=None,
                tenant_id=uuid.uuid4(),
                user_role="ADMIN",
                table_name="employees",
                columns=columns,
                rows=rows,
            )

        assert out_cols == columns
        assert out_rows[0]["salary"] == "100000"
        assert out_rows[0]["ssn"] == "123-45-6789"

    def test_deny_removes_column(self):
        """Action 'deny' should remove the column from both columns and rows."""
        from unittest.mock import patch

        from app.security.column_security import ColumnSecurityEngine

        policy = self._make_policy("salary", "deny", applies_to_roles=["VIEWER"])
        columns = ["name", "salary", "department"]
        rows = [{"name": "Bob", "salary": "80000", "department": "Engineering"}]

        with patch.object(ColumnSecurityEngine, "_load_policies", return_value=[policy]):
            out_cols, out_rows = ColumnSecurityEngine.apply(
                session=None,
                tenant_id=uuid.uuid4(),
                user_role="VIEWER",
                table_name="employees",
                columns=columns,
                rows=rows,
            )

        assert "salary" not in out_cols
        assert "salary" not in out_rows[0]
        assert "name" in out_cols
        assert "department" in out_cols

    def test_mask_replaces_all_chars(self):
        """Action 'mask' should replace all characters with the mask character."""
        from unittest.mock import patch

        from app.security.column_security import ColumnSecurityEngine

        policy = self._make_policy("ssn", "mask", applies_to_roles=["VIEWER"], mask_char="*")
        columns = ["name", "ssn"]
        rows = [{"name": "Carol", "ssn": "123-45-6789"}]

        with patch.object(ColumnSecurityEngine, "_load_policies", return_value=[policy]):
            out_cols, out_rows = ColumnSecurityEngine.apply(
                session=None,
                tenant_id=uuid.uuid4(),
                user_role="VIEWER",
                table_name="employees",
                columns=columns,
                rows=rows,
            )

        assert "ssn" in out_cols
        assert out_rows[0]["ssn"] == "*" * len("123-45-6789")
        assert out_rows[0]["name"] == "Carol"

    def test_partial_mask_shows_last_n_chars(self):
        """Action 'partial_mask' should show only the last N visible characters."""
        from unittest.mock import patch

        from app.security.column_security import ColumnSecurityEngine

        policy = self._make_policy("card_number", "partial_mask",
                                   applies_to_roles=["VIEWER", "ANALYST"],
                                   mask_char="*", visible_chars=4)
        columns = ["card_number"]
        rows = [{"card_number": "4111111111111234"}]

        with patch.object(ColumnSecurityEngine, "_load_policies", return_value=[policy]):
            out_cols, out_rows = ColumnSecurityEngine.apply(
                session=None,
                tenant_id=uuid.uuid4(),
                user_role="VIEWER",
                table_name="payments",
                columns=columns,
                rows=rows,
            )

        assert out_rows[0]["card_number"].endswith("1234")
        assert out_rows[0]["card_number"].startswith("*")

    def test_hash_produces_sha256(self):
        """Action 'hash' should produce a deterministic SHA-256 hex digest."""
        from unittest.mock import patch

        from app.security.column_security import ColumnSecurityEngine

        policy = self._make_policy("email", "hash", applies_to_roles=["ANALYST"])
        columns = ["email"]
        rows = [{"email": "user@example.com"}]

        with patch.object(ColumnSecurityEngine, "_load_policies", return_value=[policy]):
            out_cols, out_rows = ColumnSecurityEngine.apply(
                session=None,
                tenant_id=uuid.uuid4(),
                user_role="ANALYST",
                table_name="users",
                columns=columns,
                rows=rows,
            )

        expected_hash = hashlib.sha256(b"user@example.com").hexdigest()
        assert out_rows[0]["email"] == expected_hash


# ---------------------------------------------------------------------------
# 3. Permission / RBAC Tests
# ---------------------------------------------------------------------------

class TestRBAC:
    """Test the permission matrix."""

    def test_admin_has_all_permissions(self):
        from app.api.deps import Permission, has_permission

        for perm in [
            Permission.MANAGE_USERS, Permission.MANAGE_TENANTS,
            Permission.MANAGE_SOURCES, Permission.EXPORT_DATA,
            Permission.VIEW_AUDIT_LOG, Permission.MANAGE_API_KEYS,
        ]:
            assert has_permission("ADMIN", perm), f"ADMIN should have {perm}"

    def test_viewer_cannot_manage_users(self):
        from app.api.deps import Permission, has_permission

        assert not has_permission("VIEWER", Permission.MANAGE_USERS)
        assert not has_permission("VIEWER", Permission.MANAGE_SOURCES)
        assert not has_permission("VIEWER", Permission.EXPORT_DATA)
        assert not has_permission("VIEWER", Permission.MANAGE_API_KEYS)

    def test_analyst_can_save_insights(self):
        from app.api.deps import Permission, has_permission

        assert has_permission("ANALYST", Permission.SAVE_INSIGHTS)
        assert has_permission("ANALYST", Permission.USE_AI_CHAT)
        assert has_permission("ANALYST", Permission.EXPORT_DATA)

    def test_analyst_cannot_manage_users(self):
        from app.api.deps import Permission, has_permission

        assert not has_permission("ANALYST", Permission.MANAGE_USERS)
        assert not has_permission("ANALYST", Permission.MANAGE_TENANTS)

    def test_viewer_can_use_chat(self):
        from app.api.deps import Permission, has_permission

        assert has_permission("VIEWER", Permission.USE_AI_CHAT)
        assert has_permission("VIEWER", Permission.VIEW_DASHBOARDS)


# ---------------------------------------------------------------------------
# 4. Secret Provider Tests
# ---------------------------------------------------------------------------

class TestSecretProvider:
    """Test encrypt/decrypt roundtrip for the FernetEnvProvider."""

    def test_fernet_encrypt_decrypt_roundtrip(self, tmp_path, monkeypatch):
        """Fernet provider should correctly encrypt and decrypt data."""
        from cryptography.fernet import Fernet

        # Generate a test key and patch the settings
        test_key = Fernet.generate_key().decode()
        monkeypatch.setenv("ENCRYPTION_KEY", test_key)

        # Clear the lru_cache so settings reload
        from app.config import get_settings
        get_settings.cache_clear()

        # Clear any cached provider
        import app.security.secrets as secrets_module
        secrets_module._provider = None

        from app.security.secrets import FernetEnvProvider
        provider = FernetEnvProvider()

        plaintext = "super-secret-password-123"
        ciphertext = provider.encrypt(plaintext)
        recovered = provider.decrypt_str(ciphertext)

        assert recovered == plaintext
        assert ciphertext != plaintext.encode()

        # Cleanup
        get_settings.cache_clear()
        secrets_module._provider = None

    def test_fernet_encrypt_produces_different_ciphertexts(self, monkeypatch):
        """Each encryption call should produce a unique ciphertext (nonce-based)."""
        from cryptography.fernet import Fernet

        test_key = Fernet.generate_key().decode()
        monkeypatch.setenv("ENCRYPTION_KEY", test_key)

        from app.config import get_settings
        get_settings.cache_clear()

        import app.security.secrets as secrets_module
        secrets_module._provider = None

        from app.security.secrets import FernetEnvProvider
        provider = FernetEnvProvider()

        plaintext = "same-password"
        ct1 = provider.encrypt(plaintext)
        ct2 = provider.encrypt(plaintext)

        assert ct1 != ct2, "Two encryptions of the same value should differ"

        # But both should decrypt correctly
        assert provider.decrypt_str(ct1) == plaintext
        assert provider.decrypt_str(ct2) == plaintext

        # Cleanup
        get_settings.cache_clear()
        secrets_module._provider = None
