"""add model usage budget ledger

Revision ID: f8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-07-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f8b9c0d1e2f3"
down_revision: Union[str, Sequence[str], None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    table_names = {
        "organization_usage_budget",
        "model_usage_reservation",
        "model_usage_record",
    }
    existing_tables = table_names & set(sa.inspect(bind).get_table_names())
    if existing_tables and existing_tables != table_names:
        raise RuntimeError(
            "model usage budget ledger is partially present; repair the schema before migration"
        )

    if not existing_tables:
        op.create_table(
            "organization_usage_budget",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column(
                "org_id",
                sa.String(length=36),
                sa.ForeignKey("organization.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column("official_monthly_token_limit", sa.BigInteger(), nullable=True),
            sa.Column("byok_monthly_token_limit", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint(
                "official_monthly_token_limit IS NULL OR official_monthly_token_limit >= 0",
                name="ck_organization_usage_budget_official_tokens",
            ),
            sa.CheckConstraint(
                "byok_monthly_token_limit IS NULL OR byok_monthly_token_limit >= 0",
                name="ck_organization_usage_budget_byok_tokens",
            ),
        )

        op.create_table(
            "model_usage_reservation",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column(
                "org_id",
                sa.String(length=36),
                sa.ForeignKey("organization.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
            sa.Column("project_id", sa.String(length=36), sa.ForeignKey("project.id", ondelete="SET NULL"), nullable=True),
            sa.Column(
                "execution_run_id",
                sa.String(length=36),
                sa.ForeignKey("execution_run.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "runtime_run_id",
                sa.String(length=36),
                sa.ForeignKey("runtime_run.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("provider_source", sa.String(length=30), nullable=False),
            sa.Column("workload", sa.String(length=80), nullable=False),
            sa.Column("reservation_key", sa.String(length=255), nullable=False),
            sa.Column("reserved_tokens", sa.BigInteger(), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="reserved"),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("settled_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("org_id", "reservation_key", name="uq_model_usage_reservation_org_key"),
            sa.CheckConstraint("reserved_tokens > 0", name="ck_model_usage_reservation_tokens"),
        )

        op.create_table(
            "model_usage_record",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column(
                "org_id",
                sa.String(length=36),
                sa.ForeignKey("organization.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("user.id", ondelete="SET NULL"), nullable=True),
            sa.Column("project_id", sa.String(length=36), sa.ForeignKey("project.id", ondelete="SET NULL"), nullable=True),
            sa.Column(
                "execution_run_id",
                sa.String(length=36),
                sa.ForeignKey("execution_run.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "runtime_run_id",
                sa.String(length=36),
                sa.ForeignKey("runtime_run.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "provider_config_id",
                sa.String(length=36),
                sa.ForeignKey("provider_config.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("provider_source", sa.String(length=30), nullable=False),
            sa.Column("provider_type", sa.String(length=30), nullable=False),
            sa.Column("model_name", sa.String(length=255), nullable=False),
            sa.Column("workload", sa.String(length=80), nullable=False),
            sa.Column("input_tokens", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("output_tokens", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("reasoning_tokens", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("cache_read_tokens", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("cache_write_tokens", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("total_tokens", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("measurement_source", sa.String(length=50), nullable=False, server_default="provider_reported"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint("input_tokens >= 0", name="ck_model_usage_record_input_tokens"),
            sa.CheckConstraint("output_tokens >= 0", name="ck_model_usage_record_output_tokens"),
            sa.CheckConstraint("reasoning_tokens >= 0", name="ck_model_usage_record_reasoning_tokens"),
            sa.CheckConstraint("cache_read_tokens >= 0", name="ck_model_usage_record_cache_read_tokens"),
            sa.CheckConstraint("cache_write_tokens >= 0", name="ck_model_usage_record_cache_write_tokens"),
            sa.CheckConstraint("total_tokens >= 0", name="ck_model_usage_record_total_tokens"),
        )

    def create_index_if_missing(name: str, table: str, columns: list[str]) -> None:
        if name not in {index["name"] for index in sa.inspect(bind).get_indexes(table)}:
            op.create_index(name, table, columns)

    create_index_if_missing(
        "ix_model_usage_reservation_org_status_expiry",
        "model_usage_reservation",
        ["org_id", "status", "expires_at"],
    )
    create_index_if_missing(
        "ix_model_usage_reservation_execution_run",
        "model_usage_reservation",
        ["execution_run_id"],
    )
    create_index_if_missing(
        "ix_model_usage_reservation_runtime_run",
        "model_usage_reservation",
        ["runtime_run_id"],
    )
    create_index_if_missing(
        "ix_model_usage_record_org_source_created",
        "model_usage_record",
        ["org_id", "provider_source", "created_at"],
    )
    create_index_if_missing("ix_model_usage_record_execution_run", "model_usage_record", ["execution_run_id"])
    create_index_if_missing("ix_model_usage_record_runtime_run", "model_usage_record", ["runtime_run_id"])


def downgrade() -> None:
    op.drop_index("ix_model_usage_record_runtime_run", table_name="model_usage_record")
    op.drop_index("ix_model_usage_record_execution_run", table_name="model_usage_record")
    op.drop_index("ix_model_usage_record_org_source_created", table_name="model_usage_record")
    op.drop_table("model_usage_record")

    op.drop_index("ix_model_usage_reservation_runtime_run", table_name="model_usage_reservation")
    op.drop_index("ix_model_usage_reservation_execution_run", table_name="model_usage_reservation")
    op.drop_index("ix_model_usage_reservation_org_status_expiry", table_name="model_usage_reservation")
    op.drop_table("model_usage_reservation")
    op.drop_table("organization_usage_budget")
