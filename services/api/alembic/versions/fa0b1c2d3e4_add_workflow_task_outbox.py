"""add workflow task outbox

Revision ID: fa0b1c2d3e4
Revises: f9a0b1c2d3e4
Create Date: 2026-07-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "fa0b1c2d3e4"
down_revision: Union[str, Sequence[str], None] = "f9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("task_outbox_event"):
        op.create_table(
            "task_outbox_event",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column(
                "org_id",
                sa.String(length=36),
                sa.ForeignKey("organization.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "project_id",
                sa.String(length=36),
                sa.ForeignKey("project.id", ondelete="SET NULL"),
                nullable=True,
            ),
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
            sa.Column("task_name", sa.String(length=200), nullable=False),
            sa.Column("args_json", sa.JSON(), nullable=False),
            sa.Column("kwargs_json", sa.JSON(), nullable=False),
            sa.Column("deduplication_key", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("dispatch_attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("available_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
            sa.Column("last_error_code", sa.String(length=100), nullable=True),
            sa.Column("dispatched_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("org_id", "deduplication_key", name="uq_task_outbox_org_deduplication"),
            sa.CheckConstraint("dispatch_attempts >= 0", name="ck_task_outbox_dispatch_attempts"),
            sa.CheckConstraint("delivery_attempts >= 0", name="ck_task_outbox_delivery_attempts"),
        )
    existing_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("task_outbox_event")}
    if "ix_task_outbox_status_available" not in existing_indexes:
        op.create_index("ix_task_outbox_status_available", "task_outbox_event", ["status", "available_at"])
    if "ix_task_outbox_execution_run" not in existing_indexes:
        op.create_index("ix_task_outbox_execution_run", "task_outbox_event", ["execution_run_id"])


def downgrade() -> None:
    op.drop_index("ix_task_outbox_execution_run", table_name="task_outbox_event")
    op.drop_index("ix_task_outbox_status_available", table_name="task_outbox_event")
    op.drop_table("task_outbox_event")
