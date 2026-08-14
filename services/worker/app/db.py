import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker



DATABASE_URL = os.environ.get(
    "DOCPILOT_DATABASE_URL",
    "postgresql+psycopg://docpilot:docpilot@localhost:5433/docpilot",
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI-compatible session dependency for shared domain services."""
    yield from get_session()
