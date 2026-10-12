"""SQLAlchemy engine + session management.

The engine is created lazily from the resolved settings URL, so tests can
point `DATABASE_URL` at a temporary SQLite file before importing the app.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.errors import DatabaseUnavailableError
from app.logging_config import get_logger

logger = get_logger(__name__)

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Return (and lazily create) the process-wide engine."""
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        url = settings.sqlalchemy_url
        kwargs: dict = {"pool_pre_ping": True, "future": True}
        if url.startswith("sqlite"):
            # Required so the same SQLite connection is visible across threads
            # (FastAPI runs sync endpoints in a threadpool).
            kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
        else:
            kwargs.update({"pool_size": 5, "max_overflow": 10})
        _engine = create_engine(url, **kwargs)

        if url.startswith("sqlite"):
            # Enforce foreign keys + WAL for the local fallback database.
            @event.listens_for(_engine, "connect")
            def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - driver hook
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA busy_timeout=30000")
                cursor.close()

        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
        logger.info(
            "Database engine ready (%s).",
            "sqlite-fallback" if settings.is_sqlite else "postgresql",
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a database session."""
    session = get_session_factory()()
    try:
        yield session
    except DatabaseUnavailableError:
        raise
    except SQLAlchemyError as exc:
        session.rollback()
        bind = session.get_bind()
        logger.exception(
            "Database request failed.",
            extra={
                "database": bind.dialect.name,
                "database_driver": bind.dialect.driver,
                "error_type": type(exc).__name__,
            },
        )
        raise DatabaseUnavailableError(
            "The database request failed. Check database connectivity and try again."
        ) from exc
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager for scripts / background work."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_database() -> tuple[bool, str | None]:
    """Health probe: returns (ok, error_message)."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:  # pragma: no cover - depends on environment
        logger.warning("Database health check failed: %s", exc)
        return False, str(exc)


def dispose_engine() -> None:
    """Drop the engine (used on shutdown and between tests)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
