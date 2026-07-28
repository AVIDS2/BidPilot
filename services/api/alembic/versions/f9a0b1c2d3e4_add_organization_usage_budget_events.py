"""add organization usage budget audit events

Revision ID: f9a0b1c2d3e4
Revises: f8b9c0d1e2f3
Create Date: 2026-07-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f9a0b1c2d3e4"
down_revision: Union[str, Sequence[str], None] = "f8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("organization_usage_budget_event"):
        op.create_table(
            "organization_usage_budget_event",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column(
                "org_id",
                sa.String(length=36),
                sa.ForeignKey("organization.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "actor_user_id",
                sa.String(length=36),
                sa.ForeignKey("user.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("event_type", sa.String(length=100), nullable=False),
            sa.Column("previous_limits_json", sa.JSON(), nullable=False),
            sa.Column("updated_limits_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
    if "ix_organization_usage_budget_event_org_created" not in {
        index["name"]
        for index in sa.inspect(bind).get_indexes("organization_usage_budget_event")
    }:
        op.create_index(
            "ix_organization_usage_budget_event_org_created",
            "organization_usage_budget_event",
            ["org_id", "created_at"],
        )


def downgrade() -> None:
    op.drop_index(
        "ix_organization_usage_budget_event_org_created",
        table_name="organization_usage_budget_event",
    )
    op.drop_table("organization_usage_budget_event")
