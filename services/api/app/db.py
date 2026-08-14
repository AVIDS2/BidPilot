import os
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from contracts.db import Base

__all__ = ["Base", "DATABASE_URL", "SessionLocal", "engine", "get_db"]

DATABASE_URL = os.environ.get(
    "DOCPILOT_DATABASE_URL",
    "postgresql+psycopg://docpilot:docpilot@localhost:5433/docpilot",
)

engine = create_engine(DATABASE_URL)

if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        """Keep local SQLite semantics aligned with PostgreSQL foreign keys."""
        previous_autocommit = getattr(dbapi_connection, "autocommit", None)
        if previous_autocommit is not None:
            dbapi_connection.autocommit = True
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        finally:
            if previous_autocommit is not None:
                dbapi_connection.autocommit = previous_autocommit

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
