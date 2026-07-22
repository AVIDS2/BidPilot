"""add unified runtime control plane

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-07-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, Sequence[str], None] = "d7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "runtime_run",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="queued"),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("organization.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("project.id", ondelete="SET NULL")),
        sa.Column("conversation_id", sa.String(length=36), sa.ForeignKey("chat_conversation.id", ondelete="SET NULL")),
        sa.Column("parent_run_id", sa.String(length=36), sa.ForeignKey("runtime_run.id", ondelete="SET NULL")),
        sa.Column("execution_run_id", sa.String(length=36), sa.ForeignKey("execution_run.id", ondelete="SET NULL")),
        sa.Column("engine", sa.String(length=80), nullable=False),
        sa.Column("trace_id", sa.String(length=100), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255)),
        sa.Column("provider_config_id", sa.String(length=36), sa.ForeignKey("provider_config.id", ondelete="SET NULL")),
        sa.Column("model", sa.String(length=255)),
        sa.Column("reasoning_effort", sa.String(length=30)),
        sa.Column("policy_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("input_json", sa.JSON()),
        sa.Column("result_json", sa.JSON()),
        sa.Column("error_code", sa.String(length=100)),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("finished_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("org_id", "idempotency_key", name="uq_runtime_run_org_idempotency"),
    )
    op.create_index("ix_runtime_run_org_status_created", "runtime_run", ["org_id", "status", "created_at"])
    op.create_index("ix_runtime_run_project_created", "runtime_run", ["project_id", "created_at"])
    op.create_index("ix_runtime_run_conversation_created", "runtime_run", ["conversation_id", "created_at"])

    op.create_table(
        "runtime_event",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("runtime_run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("public_summary", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("schema_version", sa.String(length=20), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("run_id", "sequence", name="uq_runtime_event_run_sequence"),
    )
    op.create_index("ix_runtime_event_run_sequence", "runtime_event", ["run_id", "sequence"])

    op.create_table(
        "runtime_action",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("runtime_run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_key", sa.String(length=255), nullable=False),
        sa.Column("capability_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("risk_level", sa.String(length=40), nullable=False),
        sa.Column("policy_outcome", sa.String(length=40), nullable=False),
        sa.Column("approval_mode", sa.String(length=40), nullable=False),
        sa.Column("arguments_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON()),
        sa.Column("public_summary", sa.Text()),
        sa.Column("error_code", sa.String(length=100)),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime()),
        sa.UniqueConstraint("run_id", "action_key", name="uq_runtime_action_run_action_key"),
    )
    op.create_index("ix_runtime_action_run_status", "runtime_action", ["run_id", "status"])

    op.create_table(
        "runtime_approval",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("action_id", sa.String(length=36), sa.ForeignKey("runtime_action.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("organization.id"), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("decision_json", sa.JSON()),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("action_id", name="uq_runtime_approval_action"),
    )
    op.create_index("ix_runtime_approval_user_status", "runtime_approval", ["user_id", "status"])
    op.create_index("ix_runtime_approval_org_status", "runtime_approval", ["org_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_runtime_approval_org_status", table_name="runtime_approval")
    op.drop_index("ix_runtime_approval_user_status", table_name="runtime_approval")
    op.drop_table("runtime_approval")
    op.drop_index("ix_runtime_action_run_status", table_name="runtime_action")
    op.drop_table("runtime_action")
    op.drop_index("ix_runtime_event_run_sequence", table_name="runtime_event")
    op.drop_table("runtime_event")
    op.drop_index("ix_runtime_run_conversation_created", table_name="runtime_run")
    op.drop_index("ix_runtime_run_project_created", table_name="runtime_run")
    op.drop_index("ix_runtime_run_org_status_created", table_name="runtime_run")
    op.drop_table("runtime_run")
