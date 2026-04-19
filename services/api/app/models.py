from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Project(Base):
    __tablename__ = "project"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
