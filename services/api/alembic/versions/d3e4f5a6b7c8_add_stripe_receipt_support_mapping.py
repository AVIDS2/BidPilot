"""add support mapping to Stripe webhook receipts

Revision ID: d3e4f5a6b7c8
Revises: d2e3f4a5b6c7
Create Date: 2026-07-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "stripe_webhook_event",
        sa.Column("user_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "stripe_webhook_event",
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "stripe_webhook_event",
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
    )
    op.create_foreign_key(
        "fk_stripe_webhook_event_user_id",
        "stripe_webhook_event",
        "user",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_stripe_webhook_event_user_received",
        "stripe_webhook_event",
        ["user_id", "received_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_stripe_webhook_event_user_received", table_name="stripe_webhook_event")
    op.drop_constraint(
        "fk_stripe_webhook_event_user_id",
        "stripe_webhook_event",
        type_="foreignkey",
    )
    op.drop_column("stripe_webhook_event", "stripe_subscription_id")
    op.drop_column("stripe_webhook_event", "stripe_customer_id")
    op.drop_column("stripe_webhook_event", "user_id")
