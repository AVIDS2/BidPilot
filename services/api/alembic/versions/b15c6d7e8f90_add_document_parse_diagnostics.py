"""add durable document parser diagnostics

Revision ID: b15c6d7e8f90
Revises: a04b5c6d7e8f
Create Date: 2026-08-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b15c6d7e8f90"
down_revision: Union[str, Sequence[str], None] = "a04b5c6d7e8f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    columns = _columns("source_document")
    if "parser_name" not in columns:
        op.add_column("source_document", sa.Column("parser_name", sa.String(length=100), nullable=True))
    if "parser_version" not in columns:
        op.add_column("source_document", sa.Column("parser_version", sa.String(length=50), nullable=True))
    if "parse_error_detail" not in columns:
        op.add_column("source_document", sa.Column("parse_error_detail", sa.Text(), nullable=True))
    if "parse_retryable" not in columns:
        op.add_column(
            "source_document",
            sa.Column("parse_retryable", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
    op.execute("UPDATE source_document SET parse_retryable = true WHERE parse_retryable IS NULL")


def downgrade() -> None:
    columns = _columns("source_document")
    for column_name in ("parse_retryable", "parse_error_detail", "parser_version", "parser_name"):
        if column_name in columns:
            op.drop_column("source_document", column_name)
