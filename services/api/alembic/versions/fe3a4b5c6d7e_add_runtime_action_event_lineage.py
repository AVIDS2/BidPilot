"""add runtime action event lineage

Revision ID: fe3a4b5c6d7e
Revises: fd2e3f4a5b6c
Create Date: 2026-08-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "fe3a4b5c6d7e"
down_revision: Union[str, Sequence[str], None] = "fd2e3f4a5b6c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    columns = _columns("runtime_action")
    if "parent_event_id" not in columns:
        op.add_column(
            "runtime_action",
            sa.Column("parent_event_id", sa.String(length=36), nullable=True),
        )
    if "turn_id" not in columns:
        op.add_column(
            "runtime_action",
            sa.Column("turn_id", sa.String(length=64), nullable=True),
        )


def downgrade() -> None:
    columns = _columns("runtime_action")
    if "turn_id" in columns:
        op.drop_column("runtime_action", "turn_id")
    if "parent_event_id" in columns:
        op.drop_column("runtime_action", "parent_event_id")
