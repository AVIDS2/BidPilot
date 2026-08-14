"""persist attachment snapshots with chat messages

Revision ID: a17c9d2e4f6b
Revises: a16b7c8d9e0
Create Date: 2026-08-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a17c9d2e4f6b"
down_revision: Union[str, Sequence[str], None] = "a16b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    chat_columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("chat_message")}
    if "runtime_run_id" not in chat_columns:
        op.add_column(
            "chat_message",
            sa.Column("runtime_run_id", sa.String(length=36), nullable=True),
        )
        op.create_foreign_key(
            "fk_chat_message_runtime_run_id",
            "chat_message",
            "runtime_run",
            ["runtime_run_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_chat_message_runtime_run_id", "chat_message", ["runtime_run_id"])
    op.create_table(
        "chat_message_attachment",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("chat_message_id", sa.String(length=36), nullable=False),
        sa.Column("assistant_attachment_id", sa.String(length=36), nullable=True),
        sa.Column("document_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("extraction_status", sa.String(length=30), nullable=False),
        sa.Column("extracted_text", sa.Text(), server_default="", nullable=False),
        sa.Column("extraction_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assistant_attachment_id"], ["assistant_attachment.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["chat_message_id"], ["chat_message.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["source_document.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_message_attachment_chat_message_id", "chat_message_attachment", ["chat_message_id"])
    op.create_index("ix_chat_message_attachment_assistant_attachment_id", "chat_message_attachment", ["assistant_attachment_id"])
    op.create_index("ix_chat_message_attachment_document_id", "chat_message_attachment", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_message_attachment_document_id", table_name="chat_message_attachment")
    op.drop_index("ix_chat_message_attachment_assistant_attachment_id", table_name="chat_message_attachment")
    op.drop_index("ix_chat_message_attachment_chat_message_id", table_name="chat_message_attachment")
    op.drop_table("chat_message_attachment")
    chat_columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("chat_message")}
    if "runtime_run_id" in chat_columns:
        op.drop_index("ix_chat_message_runtime_run_id", table_name="chat_message")
        op.drop_constraint("fk_chat_message_runtime_run_id", "chat_message", type_="foreignkey")
        op.drop_column("chat_message", "runtime_run_id")
