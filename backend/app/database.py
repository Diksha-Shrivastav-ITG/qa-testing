from __future__ import annotations

from collections.abc import Generator
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Engine & session factory are created lazily so that this module can be
# imported (e.g. by Alembic) without a live database driver being available.
# ---------------------------------------------------------------------------

_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None  # type: ignore[type-arg]


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> sessionmaker:  # type: ignore[type-arg]
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal


# Convenience alias kept for code that does ``from app.database import SessionLocal``
class SessionLocal:  # type: ignore[no-redef]
    """Proxy that forwards construction to the lazily-created session factory."""

    def __new__(cls, *args, **kwargs):  # type: ignore[override]
        return get_session_factory()(*args, **kwargs)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
