"""Database engine / session management (SQLAlchemy 2.x).

The application code only speaks SQLAlchemy ORM — the concrete database is an
environment variable.  SQLite is the zero-config default; PostgreSQL is the
recommended production target.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _make_engine(url: str):
    kwargs: dict = {"future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:  # pragma: no cover - exercised only with external DB
        kwargs["pool_pre_ping"] = True
    return create_engine(url, **kwargs)


settings = get_settings()
engine = _make_engine(settings.database_url)

if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - trivial
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def utcnow() -> datetime:
    """Timezone-aware UTC now (for API output and audit)."""
    return datetime.now(timezone.utc)


def naive_utcnow() -> datetime:
    """Naive UTC now — used for SQL comparisons, since SQLite stores
    DateTime columns without timezone info."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_naive(dt: datetime | None) -> datetime | None:
    """Normalize any datetime (naive or aware) to naive UTC."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def get_db():
    """FastAPI dependency yielding a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
