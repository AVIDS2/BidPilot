import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from contracts.db import Base


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
