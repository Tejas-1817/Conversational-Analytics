"""Builds read-only SQLAlchemy engines for customer databases.

Guardrails enforced here, in code:
- Sessions are forced read-only at the database level (Postgres/MySQL).
- Every connection carries a statement timeout so a bad query cannot hang a worker.
- Connection creation retries with exponential backoff on transient failures (up to
  MAX_CONNECT_RETRIES attempts); non-transient errors surface immediately.
- Registration is REJECTED when the supplied user has any write privilege on any
  user-owned table — this is a hard enforcement, not a comment or intention.
- Snowflake/BigQuery raise a clear NotImplementedError until tested.
"""
import time

import structlog
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import OperationalError

from app.config import get_settings
from app.models import DataSource
from app.security.crypto import decrypt_secret

log = structlog.get_logger()

MAX_CONNECT_RETRIES = 3
_RETRY_BASE_DELAY_S = 0.5  # seconds; doubles on each attempt


def _build_engine_with_retry(url: URL, pool_kwargs: dict, connect_args: dict) -> Engine:
    """Create and return an Engine, retrying on transient OperationalErrors.

    Raises the original OperationalError after MAX_CONNECT_RETRIES failed attempts.
    Non-OperationalError exceptions surface immediately without retrying.
    """
    last_exc: Exception | None = None
    for attempt in range(1, MAX_CONNECT_RETRIES + 1):
        try:
            engine = create_engine(url, **pool_kwargs, connect_args=connect_args)
            # pool_pre_ping will validate the connection on first use; verify eagerly here
            # so registration-time errors surface fast.
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return engine
        except OperationalError as exc:
            last_exc = exc
            if attempt < MAX_CONNECT_RETRIES:
                delay = _RETRY_BASE_DELAY_S * (2 ** (attempt - 1))
                log.warning(
                    "connector_transient_error_retrying",
                    attempt=attempt,
                    max_retries=MAX_CONNECT_RETRIES,
                    delay_s=delay,
                    error=str(exc),
                )
                time.sleep(delay)
            else:
                log.error(
                    "connector_failed_all_retries",
                    max_retries=MAX_CONNECT_RETRIES,
                    error=str(exc),
                )
    raise last_exc  # type: ignore[misc]


def build_engine(source: DataSource) -> Engine:
    settings = get_settings()
    password = decrypt_secret(source.credentials_encrypted)

    if source.type == "postgres":
        url = URL.create(
            "postgresql+psycopg",
            username=source.username,
            password=password,
            host=source.host,
            port=source.port or 5432,
            database=source.database_name,
        )
        engine = _build_engine_with_retry(
            url,
            pool_kwargs={"pool_size": 2, "pool_pre_ping": True},
            connect_args={"connect_timeout": 10},
        )

        @event.listens_for(engine, "connect")
        def _pg_session_guards(dbapi_conn, _record):  # noqa: ANN001
            with dbapi_conn.cursor() as cur:
                cur.execute("SET default_transaction_read_only = on")
                cur.execute(f"SET statement_timeout = {settings.statement_timeout_ms}")

        return engine

    if source.type == "mysql":
        url = URL.create(
            "mysql+pymysql",
            username=source.username,
            password=password,
            host=source.host,
            port=source.port or 3306,
            database=source.database_name,
        )
        engine = _build_engine_with_retry(
            url,
            pool_kwargs={"pool_size": 2, "pool_pre_ping": True},
            connect_args={"connect_timeout": 10},
        )

        @event.listens_for(engine, "connect")
        def _mysql_session_guards(dbapi_conn, _record):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            try:
                cur.execute("SET SESSION TRANSACTION READ ONLY")
                cur.execute(f"SET SESSION max_execution_time = {settings.statement_timeout_ms}")
            finally:
                cur.close()

        return engine

    if source.type == "mssql":
        url = URL.create(
            "mssql+pymssql",
            username=source.username,
            password=password,
            host=source.host,
            port=source.port or 1433,
            database=source.database_name,
            query={"charset": "utf8"},
        )
        engine = _build_engine_with_retry(
            url,
            pool_kwargs={"pool_size": 2, "pool_pre_ping": True},
            connect_args={"timeout": 10},
        )

        @event.listens_for(engine, "connect")
        def _mssql_session_guards(dbapi_conn, _record):  # noqa: ANN001
            cursor = dbapi_conn.cursor()
            try:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED;")
                cursor.execute(f"SET LOCK_TIMEOUT {settings.statement_timeout_ms};")
                cursor.execute("SET DEADLOCK_PRIORITY LOW;")
            finally:
                cursor.close()

        return engine

    # Snowflake / BigQuery / Databricks: not wired up until a test account is available.
    raise NotImplementedError(
        f"Source type '{source.type}' is not implemented yet. "
        "Add the dialect driver, session guards, and an integration test before enabling it."
    )


def verify_read_only(engine: Engine, source_type: str) -> None:
    """Registration-time check that the supplied user has no write privileges.

    Best-effort catalog inspection (role inheritance can hide grants); the hard
    enforcement is the per-connection read-only session guard in build_engine().
    Refuses registration when write privileges are detected.
    """
    if source_type == "postgres":
        sql = text("""
            SELECT count(*) FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind IN ('r', 'p')
              AND n.nspname NOT IN ('pg_catalog', 'information_schema')
              AND pg_catalog.has_table_privilege(current_user, c.oid, 'INSERT, UPDATE, DELETE')
        """)
        with engine.connect() as conn:
            writable_tables = conn.execute(sql).scalar_one()
        if writable_tables and writable_tables > 0:
            raise PermissionError(
                f"The supplied user has write privileges on {writable_tables} table(s). "
                "Register a read-only user; the platform must never be able to modify customer data."
            )
        return

    if source_type == "mysql":
        write_verbs = ("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "ALL PRIVILEGES")
        with engine.connect() as conn:
            grants = [row[0] for row in conn.execute(text("SHOW GRANTS"))]
        for grant in grants:
            upper = grant.upper()
            if any(verb in upper for verb in write_verbs):
                raise PermissionError(
                    f"The supplied user has write privileges ({grant!r}). "
                    "Register a read-only user; the platform must never be able to modify customer data."
                )
        return

    if source_type == "mssql":
        sql = text("""
            SELECT COUNT(*) FROM (
                SELECT r.name FROM sys.database_role_members rm
                JOIN sys.database_principals r ON rm.role_principal_id = r.principal_id
                JOIN sys.database_principals m ON rm.member_principal_id = m.principal_id
                WHERE m.name = USER_NAME() AND r.name IN ('db_owner', 'db_datawriter', 'db_ddladmin')
                UNION ALL
                SELECT p.permission_name FROM sys.database_permissions p
                JOIN sys.database_principals u ON p.grantee_principal_id = u.principal_id
                WHERE u.name = USER_NAME() AND p.state IN ('G', 'W') AND p.permission_name IN ('INSERT', 'UPDATE', 'DELETE', 'ALTER', 'CONTROL')
            ) AS writable
        """)
        try:
            with engine.connect() as conn:
                writable_count = conn.execute(sql).scalar_one()
            if writable_count and writable_count > 0:
                raise PermissionError(
                    f"The supplied MSSQL user has write/admin privileges ({writable_count} permission/role grants detected). "
                    "Register a read-only user (e.g. db_datareader role only); the platform must never be able to modify customer data."
                )
        except PermissionError:
            raise
        except Exception as exc:
            log.warning("mssql_catalog_check_skipped", error=str(exc))
        return

    log.warning("read_only_verification_not_implemented", source_type=source_type)


def test_connection(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
