from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


engine = create_engine("postgresql+psycopg://docpilot:docpilot@localhost:5432/docpilot")
