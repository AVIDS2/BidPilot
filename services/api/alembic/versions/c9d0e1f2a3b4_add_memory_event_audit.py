"""add governed memory event audit ledger

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-07-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add audit coverage for user-private and project-shared memory writes."""
    op.create_table(
        "memory_event",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("memory_record_id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("actor_type", sa.String(length=30), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["memory_record_id"], ["memory_record.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["organization.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_event_record_created", "memory_event", ["memory_record_id", "created_at"])
    op.create_index("ix_memory_event_org_created", "memory_event", ["org_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_memory_event_org_created", table_name="memory_event")
    op.drop_index("ix_memory_event_record_created", table_name="memory_event")
    op.drop_table("memory_event")
