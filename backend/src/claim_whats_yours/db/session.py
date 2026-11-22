"""Database engine and session factory."""

from collections.abc import Iterator
from functools import cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from claim_whats_yours.core.config import get_settings


def make_engine(url: str) -> Engine:
    """Create a SQLAlchemy engine for the given database URL."""
    return create_engine(
        url,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
    )


@cache
def get_session_factory(url: str) -> sessionmaker[Session]:
    """Return a cached session factory bound to an engine for the given URL."""
    return sessionmaker(bind=make_engine(url), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Yield a database session from the configured URL and close it afterwards."""
    url = get_settings().database_url
    session = get_session_factory(url)()
    try:
        yield session
    finally:
        session.close()
