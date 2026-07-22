"""add organization subscription entitlement records

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organization_subscription",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(length=36),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("plan", sa.String(length=30), nullable=False, server_default="starter"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("seat_limit", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("billable_seat_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "billing_owner_user_id",
            sa.String(length=36),
            sa.ForeignKey("user.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True, unique=True),
        sa.Column("stripe_subscription_item_id", sa.String(length=255), nullable=True, unique=True),
        sa.Column("stripe_state_event_created_at", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("seat_limit >= 1", name="ck_organization_subscription_seat_limit"),
        sa.CheckConstraint(
            "billable_seat_count >= 0",
            name="ck_organization_subscription_billable_seat_count",
        ),
    )
    op.create_index(
        "ix_organization_subscription_billing_owner",
        "organization_subscription",
        ["billing_owner_user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_organization_subscription_billing_owner",
        table_name="organization_subscription",
    )
    op.drop_table("organization_subscription")
