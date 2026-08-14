"""add chat checkpoint lineage

Revision ID: a15b6c7d8e9
Revises: c26d7e8f9012
Create Date: 2026-08-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a15b6c7d8e9"
down_revision: Union[str, Sequence[str], None] = "c26d7e8f9012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    columns = _columns("chat_conversation")
    if "source_conversation_id" not in columns:
        op.add_column(
            "chat_conversation",
            sa.Column(
                "source_conversation_id",
                sa.String(length=36),
                sa.ForeignKey("chat_conversation.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
    if "checkpoint_message_id" not in columns:
        op.add_column(
            "chat_conversation",
            sa.Column(
                "checkpoint_message_id",
                sa.String(length=36),
                sa.ForeignKey("chat_message.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    columns = _columns("chat_conversation")
    if "checkpoint_message_id" in columns:
        op.drop_column("chat_conversation", "checkpoint_message_id")
    if "source_conversation_id" in columns:
        op.drop_column("chat_conversation", "source_conversation_id")
