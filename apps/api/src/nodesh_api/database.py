"""SQLAlchemy session setup for Nodesh's modular monolith."""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from nodesh_api.config import get_settings


class Base(DeclarativeBase):
    """Base class for persisted Nodesh domain models."""


db_url = get_settings().database_url
connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
engine = create_engine(db_url, pool_pre_ping=True, connect_args=connect_args)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, _connection_record):  # type: ignore[no-untyped-def]
    if db_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    """Provide a database session for a single request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
