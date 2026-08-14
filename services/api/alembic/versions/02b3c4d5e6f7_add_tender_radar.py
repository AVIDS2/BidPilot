"""add tender radar sources, subscriptions, notices and matches

Revision ID: 02b3c4d5e6f7
Revises: 01a2b3c4d5e6
Create Date: 2026-08-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "02b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "01a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("notice_source"):
        op.create_table(
            "notice_source",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("org_id", sa.String(length=36), sa.ForeignKey("organization.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("kind", sa.String(length=30), nullable=False),
            sa.Column("endpoint_url", sa.String(length=2048), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("polling_interval_minutes", sa.Integer(), nullable=False, server_default="60"),
            sa.Column("last_polled_at", sa.DateTime(), nullable=True),
            sa.Column("last_success_at", sa.DateTime(), nullable=True),
            sa.Column("last_error_code", sa.String(length=100), nullable=True),
            sa.Column("created_by_user_id", sa.String(length=36), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("kind IN ('rss', 'json_feed', 'webhook')", name="ck_notice_source_kind"),
            sa.CheckConstraint("polling_interval_minutes BETWEEN 5 AND 1440", name="ck_notice_source_interval"),
        )
        op.create_index("ix_notice_source_org_active", "notice_source", ["org_id", "is_active"])
    if not inspector.has_table("notice_subscription"):
        op.create_table(
            "notice_subscription",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("org_id", sa.String(length=36), sa.ForeignKey("organization.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("keywords_json", sa.JSON(), nullable=False),
            sa.Column("regions_json", sa.JSON(), nullable=False),
            sa.Column("categories_json", sa.JSON(), nullable=False),
            sa.Column("budget_min", sa.Float(), nullable=True),
            sa.Column("budget_max", sa.Float(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by_user_id", sa.String(length=36), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("budget_min IS NULL OR budget_max IS NULL OR budget_min <= budget_max", name="ck_notice_subscription_budget_range"),
        )
        op.create_index("ix_notice_subscription_org_active", "notice_subscription", ["org_id", "is_active"])
    if not inspector.has_table("notice_item"):
        op.create_table(
            "notice_item",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("org_id", sa.String(length=36), sa.ForeignKey("organization.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_id", sa.String(length=36), sa.ForeignKey("notice_source.id", ondelete="CASCADE"), nullable=False),
            sa.Column("external_id", sa.String(length=500), nullable=False),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("buyer_name", sa.String(length=255), nullable=True),
            sa.Column("notice_type", sa.String(length=40), nullable=False, server_default="other"),
            sa.Column("region", sa.String(length=120), nullable=True),
            sa.Column("category", sa.String(length=120), nullable=True),
            sa.Column("budget_amount", sa.Float(), nullable=True),
            sa.Column("published_at", sa.DateTime(), nullable=True),
            sa.Column("deadline_at", sa.DateTime(), nullable=True),
            sa.Column("source_url", sa.String(length=2048), nullable=False),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("source_snapshot_json", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="new"),
            sa.Column("saved_by_user_id", sa.String(length=36), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
            sa.Column("converted_project_id", sa.String(length=36), sa.ForeignKey("project.id", ondelete="SET NULL"), nullable=True, unique=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("notice_type IN ('intent', 'tender', 'prequalification', 'rfi', 'other')", name="ck_notice_item_type"),
            sa.CheckConstraint("status IN ('new', 'saved', 'ignored', 'converted')", name="ck_notice_item_status"),
            sa.UniqueConstraint("source_id", "external_id", name="uq_notice_item_source_external"),
        )
        op.create_index("ix_notice_item_org_status_created", "notice_item", ["org_id", "status", "created_at"])
        op.create_index("ix_notice_item_org_deadline", "notice_item", ["org_id", "deadline_at"])
    if not inspector.has_table("notice_match"):
        op.create_table(
            "notice_match",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("notice_id", sa.String(length=36), sa.ForeignKey("notice_item.id", ondelete="CASCADE"), nullable=False),
            sa.Column("subscription_id", sa.String(length=36), sa.ForeignKey("notice_subscription.id", ondelete="CASCADE"), nullable=False),
            sa.Column("score", sa.Integer(), nullable=False),
            sa.Column("reasons_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("score BETWEEN 0 AND 100", name="ck_notice_match_score"),
            sa.UniqueConstraint("notice_id", "subscription_id", name="uq_notice_match_notice_subscription"),
        )
        op.create_index("ix_notice_match_subscription_score", "notice_match", ["subscription_id", "score"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table_name in ("notice_match", "notice_item", "notice_subscription", "notice_source"):
        if inspector.has_table(table_name):
            op.drop_table(table_name)
