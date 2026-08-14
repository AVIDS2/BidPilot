"""add source document provenance

Revision ID: 01a2b3c4d5e6
Revises: a17c9d2e4f6b
Create Date: 2026-08-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "01a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "a17c9d2e4f6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    if "source_url" not in _columns("source_document"):
        op.add_column("source_document", sa.Column("source_url", sa.String(length=2048), nullable=True))


def downgrade() -> None:
    if "source_url" in _columns("source_document"):
        op.drop_column("source_document", "source_url")
