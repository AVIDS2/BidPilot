"""add persistent conversation pin state

Revision ID: a16b7c8d9e0
Revises: a15b6c7d8e9
Create Date: 2026-08-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a16b7c8d9e0"
down_revision: Union[str, Sequence[str], None] = "a15b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("chat_conversation")}
    if "is_pinned" not in columns:
        op.add_column(
            "chat_conversation",
            sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("chat_conversation")}
    if "is_pinned" in columns:
        op.drop_column("chat_conversation", "is_pinned")
