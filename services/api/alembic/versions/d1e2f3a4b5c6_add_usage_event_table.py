"""add usage event table

Revision ID: d1e2f3a4b5c6
Revises: b4c5d6e7f8a9
Create Date: 2026-06-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, Sequence[str], None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usage_event",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("organization.id"), nullable=False),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("project.id"), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("provider_source", sa.String(length=30), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("execution_run_id", sa.String(length=36), sa.ForeignKey("execution_run.id"), nullable=True),
        sa.Column("period_key", sa.String(length=7), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_usage_event_user_event_provider", "usage_event", ["user_id", "event_type", "provider_source"])
    op.create_index("ix_usage_event_org_created", "usage_event", ["org_id", "created_at"])
    op.create_index("ix_usage_event_period_key", "usage_event", ["period_key"])


def downgrade() -> None:
    op.drop_index("ix_usage_event_org_created", table_name="usage_event")
    op.drop_index("ix_usage_event_user_event_provider", table_name="usage_event")
    op.drop_table("usage_event")
