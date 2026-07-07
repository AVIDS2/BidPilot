"""add assistant audit tables

Revision ID: a4b5c6d7e8f9
Revises: f3a4b5c6d7e8
Create Date: 2026-07-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4b5c6d7e8f9"
down_revision: Union[str, Sequence[str], None] = "f3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assistant_action_audit",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.String(length=36),
            sa.ForeignKey("chat_conversation.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("organization.id"), nullable=False),
        sa.Column("tool_name", sa.String(length=80), nullable=False),
        sa.Column("risk_level", sa.String(length=30), nullable=False),
        sa.Column("approval_mode", sa.String(length=30), nullable=False, server_default="risky_only"),
        sa.Column("arguments_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="running"),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_assistant_action_audit_conversation_created",
        "assistant_action_audit",
        ["conversation_id", "created_at"],
    )
    op.create_index(
        "ix_assistant_action_audit_user_created",
        "assistant_action_audit",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_assistant_action_audit_status",
        "assistant_action_audit",
        ["status"],
    )

    op.create_table(
        "assistant_approval",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.String(length=36),
            sa.ForeignKey("chat_conversation.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "action_audit_id",
            sa.String(length=36),
            sa.ForeignKey("assistant_action_audit.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("organization.id"), nullable=False),
        sa.Column("thread_id", sa.String(length=100), nullable=False),
        sa.Column("tool_name", sa.String(length=80), nullable=False),
        sa.Column("risk_level", sa.String(length=30), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_assistant_approval_conversation_status",
        "assistant_approval",
        ["conversation_id", "status"],
    )
    op.create_index(
        "ix_assistant_approval_user_created",
        "assistant_approval",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_assistant_approval_user_created", table_name="assistant_approval")
    op.drop_index("ix_assistant_approval_conversation_status", table_name="assistant_approval")
    op.drop_table("assistant_approval")
    op.drop_index("ix_assistant_action_audit_status", table_name="assistant_action_audit")
    op.drop_index("ix_assistant_action_audit_user_created", table_name="assistant_action_audit")
    op.drop_index("ix_assistant_action_audit_conversation_created", table_name="assistant_action_audit")
    op.drop_table("assistant_action_audit")
