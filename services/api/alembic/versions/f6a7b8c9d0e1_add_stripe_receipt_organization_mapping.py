"""add organization mapping to Stripe webhook receipts

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("stripe_webhook_event")}
    if "org_id" not in columns:
        op.add_column(
            "stripe_webhook_event",
            sa.Column(
                "org_id",
                sa.String(length=36),
                sa.ForeignKey("organization.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )

    if "ix_stripe_webhook_event_org_received" not in {
        index["name"] for index in sa.inspect(op.get_bind()).get_indexes("stripe_webhook_event")
    }:
        op.create_index(
            "ix_stripe_webhook_event_org_received",
            "stripe_webhook_event",
            ["org_id", "received_at"],
        )


def downgrade() -> None:
    op.drop_index(
        "ix_stripe_webhook_event_org_received",
        table_name="stripe_webhook_event",
    )
    op.drop_column("stripe_webhook_event", "org_id")
