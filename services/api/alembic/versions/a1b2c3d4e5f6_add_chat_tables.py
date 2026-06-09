"""add chat conversation and message tables

Revision ID: a1b2c3d4e5f6
Revises: f9952f403115
Create Date: 2026-06-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f9952f403115'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "chat_conversation",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("project.id"), nullable=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_chat_conversation_user_id", "chat_conversation", ["user_id"])
    op.create_index("ix_chat_conversation_project_id", "chat_conversation", ["project_id"])

    op.create_table(
        "chat_message",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("chat_conversation.id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_chat_message_conversation_id", "chat_message", ["conversation_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("chat_message")
    op.drop_table("chat_conversation")
