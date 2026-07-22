"""add Stripe subscription mapping and webhook receipt ledger

Revision ID: d2e3f4a5b6c7
Revises: d0e1f2a3b4c5
Create Date: 2026-07-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "subscription",
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "subscription",
        sa.Column("stripe_state_event_created_at", sa.Integer(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_subscription_stripe_subscription_id",
        "subscription",
        ["stripe_subscription_id"],
    )
    op.create_table(
        "stripe_webhook_event",
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("event_created_at", sa.Integer(), nullable=False),
        sa.Column("livemode", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("outcome", sa.String(length=50), nullable=False),
        sa.Column("received_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_stripe_webhook_event_created_at",
        "stripe_webhook_event",
        ["event_created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_stripe_webhook_event_created_at", table_name="stripe_webhook_event")
    op.drop_table("stripe_webhook_event")
    op.drop_constraint(
        "uq_subscription_stripe_subscription_id",
        "subscription",
        type_="unique",
    )
    op.drop_column("subscription", "stripe_state_event_created_at")
    op.drop_column("subscription", "stripe_subscription_id")
