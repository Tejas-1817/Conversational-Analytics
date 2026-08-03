"""Metadata repository session management (our own Postgres, not customer databases)."""
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine = None
_SessionLocal: sessionmaker | None = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        db_url = get_settings().metadata_db_url
        if db_url.startswith("postgresql://"):
            try:
                import psycopg2
            except ImportError:
                # Fallback to psycopg (v3) driver if psycopg2 is not installed
                db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
        _engine = create_engine(db_url, pool_pre_ping=True, pool_size=5)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    get_engine()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """For use in worker jobs."""
    yield from get_session()
