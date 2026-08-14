"""add outbound business webhook endpoints and deliveries

Revision ID: 03c4d5e6f7a8
Revises: 02b3c4d5e6f7
Create Date: 2026-08-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "03c4d5e6f7a8"
down_revision: Union[str, Sequence[str], None] = "02b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("webhook_endpoint"):
        op.create_table(
            "webhook_endpoint",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("org_id", sa.String(length=36), sa.ForeignKey("organization.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("target_url", sa.String(length=2048), nullable=False),
            sa.Column("signing_secret_ciphertext", sa.Text(), nullable=False),
            sa.Column("events_json", sa.JSON(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by_user_id", sa.String(length=36), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_webhook_endpoint_org_active", "webhook_endpoint", ["org_id", "is_active"])
    if not inspector.has_table("webhook_delivery"):
        op.create_table(
            "webhook_delivery",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("endpoint_id", sa.String(length=36), sa.ForeignKey("webhook_endpoint.id", ondelete="CASCADE"), nullable=False),
            sa.Column("org_id", sa.String(length=36), sa.ForeignKey("organization.id", ondelete="CASCADE"), nullable=False),
            sa.Column("event_type", sa.String(length=120), nullable=False),
            sa.Column("payload_json", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("available_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
            sa.Column("last_http_status", sa.Integer(), nullable=True),
            sa.Column("last_error_code", sa.String(length=100), nullable=True),
            sa.Column("delivered_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("status IN ('pending', 'delivering', 'delivered', 'failed')", name="ck_webhook_delivery_status"),
            sa.CheckConstraint("attempt_count >= 0", name="ck_webhook_delivery_attempt_count"),
            sa.CheckConstraint("max_attempts BETWEEN 1 AND 10", name="ck_webhook_delivery_max_attempts"),
        )
        op.create_index("ix_webhook_delivery_due", "webhook_delivery", ["status", "available_at"])
        op.create_index("ix_webhook_delivery_endpoint_created", "webhook_delivery", ["endpoint_id", "created_at"])
        op.create_index("ix_webhook_delivery_org_created", "webhook_delivery", ["org_id", "created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table_name in ("webhook_delivery", "webhook_endpoint"):
        if inspector.has_table(table_name):
            op.drop_table(table_name)
