"""add per-item memory graph review decisions

Revision ID: ac2d3e4f5b6c
Revises: ab1c2d3e4f5
Create Date: 2026-07-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "ac2d3e4f5b6c"
down_revision: Union[str, Sequence[str], None] = "ab1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("memory_graph_review_decision"):
        op.create_table(
            "memory_graph_review_decision",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("org_id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("proposal_memory_record_id", sa.String(length=36), nullable=False),
            sa.Column("item_id", sa.String(length=80), nullable=False),
            sa.Column("item_type", sa.String(length=20), nullable=False),
            sa.Column("proposal_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("decision", sa.String(length=20), nullable=False),
            sa.Column("decision_note", sa.Text(), nullable=True),
            sa.Column("reviewer_user_id", sa.String(length=36), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["org_id"], ["organization.id"]),
            sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["proposal_memory_record_id"],
                ["memory_record.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(["reviewer_user_id"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "proposal_memory_record_id",
                "item_id",
                name="uq_memory_graph_review_decision_item",
            ),
        )
    existing_indexes = {
        index["name"] for index in sa.inspect(bind).get_indexes("memory_graph_review_decision")
    }
    if "ix_memory_graph_review_project_decision" not in existing_indexes:
        op.create_index(
            "ix_memory_graph_review_project_decision",
            "memory_graph_review_decision",
            ["project_id", "decision"],
        )
    if "ix_memory_graph_review_record_item" not in existing_indexes:
        op.create_index(
            "ix_memory_graph_review_record_item",
            "memory_graph_review_decision",
            ["proposal_memory_record_id", "item_type", "item_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_memory_graph_review_record_item", table_name="memory_graph_review_decision")
    op.drop_index("ix_memory_graph_review_project_decision", table_name="memory_graph_review_decision")
    op.drop_table("memory_graph_review_decision")
