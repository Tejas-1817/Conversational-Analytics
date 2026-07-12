"""Builds read-only SQLAlchemy engines for customer databases.

Guardrails enforced here, in code:
- Sessions are forced read-only at the database level (Postgres/MySQL).
- Every connection gets a statement timeout.
- Snowflake/BigQuery raise a clear NotImplementedError until their dialects are added and tested.
"""
import structlog
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine, URL

from app.config import get_settings
from app.models import DataSource
from app.security.crypto import decrypt_secret

log = structlog.get_logger()


def build_engine(source: DataSource) -> Engine:
    settings = get_settings()
    password = decrypt_secret(source.credentials_encrypted)

    if source.type == "postgres":
        url = URL.create("postgresql+psycopg", username=source.username, password=password,
                         host=source.host, port=source.port or 5432, database=source.database_name)
        engine = create_engine(url, pool_size=2, pool_pre_ping=True,
                               connect_args={"connect_timeout": 10})

        @event.listens_for(engine, "connect")
        def _pg_session_guards(dbapi_conn, _record):  # noqa: ANN001
            with dbapi_conn.cursor() as cur:
                cur.execute("SET default_transaction_read_only = on")
                cur.execute(f"SET statement_timeout = {settings.statement_timeout_ms}")

        return engine

    if source.type == "mysql":
        url = URL.create("mysql+pymysql", username=source.username, password=password,
                         host=source.host, port=source.port or 3306, database=source.database_name)
        engine = create_engine(url, pool_size=2, pool_pre_ping=True,
                               connect_args={"connect_timeout": 10})

        @event.listens_for(engine, "connect")
        def _mysql_session_guards(dbapi_conn, _record):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            try:
                cur.execute("SET SESSION TRANSACTION READ ONLY")
                cur.execute(f"SET SESSION max_execution_time = {settings.statement_timeout_ms}")
            finally:
                cur.close()

        return engine

    # Snowflake / BigQuery: dialects exist (snowflake-sqlalchemy, sqlalchemy-bigquery) but are
    # intentionally not wired up until someone on the team tests them against a real account.
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

    log.warning("read_only_verification_not_implemented", source_type=source_type)


def test_connection(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
