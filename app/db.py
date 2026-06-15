"""Database engine, session factory, and FastAPI dependency.

Models are intentionally DB-agnostic (no PostGIS types in columns) so the
same schema runs on PostgreSQL in production and SQLite in the test suite.
PostGIS-friendly coordinates are stored as plain lat/lon floats plus a
GeoJSON polygon column, which can be promoted to a `geography` column later.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

logger = logging.getLogger("agave.db")


class Base(DeclarativeBase):
    pass


def _make_engine(url: str):
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(url, pool_pre_ping=True, future=True, connect_args=connect_args)


engine = _make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db() -> None:
    """Create tables if they do not exist (dev/test convenience).

    For production use Alembic migrations instead.
    """
    from app.models import database as _models  # noqa: F401  (register mappers)

    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ensured at %s", settings.database_url.split("@")[-1])


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager for use in background tasks / services."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
