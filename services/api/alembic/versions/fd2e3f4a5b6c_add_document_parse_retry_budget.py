"""add durable document parse retry budget

Revision ID: fd2e3f4a5b6c
Revises: fc1d2e3f4a5b
Create Date: 2026-07-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "fd2e3f4a5b6c"
down_revision: Union[str, Sequence[str], None] = "fc1d2e3f4a5b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    if "parse_attempt_count" not in _columns("source_document"):
        op.add_column(
            "source_document",
            sa.Column(
                "parse_attempt_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )
    op.execute(
        "UPDATE source_document SET parse_attempt_count = 0 "
        "WHERE parse_attempt_count IS NULL"
    )


def downgrade() -> None:
    if "parse_attempt_count" in _columns("source_document"):
        op.drop_column("source_document", "parse_attempt_count")
