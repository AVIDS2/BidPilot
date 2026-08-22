"""add Mem0 profile capture ledger

Revision ID: 05e6f7a8b9c0
Revises: 04d5e6f7a8b9
Create Date: 2026-08-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "05e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "04d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "mem0_profile_sync" in inspector.get_table_names():
        return
    op.create_table(
        "mem0_profile_sync",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("runtime_run_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default="mem0_platform"),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
        sa.Column("external_event_id", sa.String(length=160), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organization.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["runtime_run_id"], ["runtime_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["chat_conversation.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("runtime_run_id", "provider", name="uq_mem0_profile_sync_run_provider"),
    )
    op.create_index(
        "ix_mem0_profile_sync_user_status_created",
        "mem0_profile_sync",
        ["org_id", "user_id", "status", "created_at"],
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "mem0_profile_sync" not in inspector.get_table_names():
        return
    op.drop_index("ix_mem0_profile_sync_user_status_created", table_name="mem0_profile_sync")
    op.drop_table("mem0_profile_sync")
