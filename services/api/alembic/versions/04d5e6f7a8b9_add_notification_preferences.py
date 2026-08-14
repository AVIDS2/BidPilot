"""add per-user notification preferences

Revision ID: 04d5e6f7a8b9
Revises: 03c4d5e6f7a8
Create Date: 2026-08-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "04d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "03c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("notification_preference"):
        return
    op.create_table(
        "notification_preference",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("in_app_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("review_updates", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("agent_updates", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("radar_updates", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("material_updates", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", name="uq_notification_preference_user"),
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("notification_preference"):
        op.drop_table("notification_preference")
