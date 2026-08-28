"""add provider tool call correlation to runtime actions

Revision ID: 06f7a8b9c0d1
Revises: 05e6f7a8b9c0
Create Date: 2026-08-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "06f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "05e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    if "tool_call_id" not in _columns("runtime_action"):
        op.add_column(
            "runtime_action",
            sa.Column("tool_call_id", sa.String(length=128), nullable=True),
        )


def downgrade() -> None:
    if "tool_call_id" in _columns("runtime_action"):
        op.drop_column("runtime_action", "tool_call_id")
