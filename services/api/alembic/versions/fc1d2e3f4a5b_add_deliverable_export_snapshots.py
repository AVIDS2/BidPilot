"""add immutable deliverable export snapshots

Revision ID: fc1d2e3f4a5b
Revises: fb0c1d2e3f4
Create Date: 2026-07-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "fc1d2e3f4a5b"
down_revision: Union[str, Sequence[str], None] = "fb0c1d2e3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "deliverable_export",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("deliverable_id", sa.String(length=36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="generating"),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("approved_versions_json", sa.JSON(), nullable=False),
        sa.Column("docx_storage_key", sa.String(length=500), nullable=True),
        sa.Column("pdf_storage_key", sa.String(length=500), nullable=True),
        sa.Column("docx_sha256", sa.String(length=64), nullable=True),
        sa.Column("pdf_sha256", sa.String(length=64), nullable=True),
        sa.Column("requested_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("client_request_id", sa.String(length=128), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deliverable_id"], ["deliverable.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "deliverable_id",
            "version_number",
            name="uq_deliverable_export_version",
        ),
        sa.UniqueConstraint(
            "deliverable_id",
            "snapshot_hash",
            name="uq_deliverable_export_snapshot",
        ),
        sa.UniqueConstraint(
            "requested_by_user_id",
            "client_request_id",
            name="uq_deliverable_export_client_request",
        ),
    )
    op.create_index("ix_deliverable_export_project_id", "deliverable_export", ["project_id"])
    op.create_index("ix_deliverable_export_deliverable_id", "deliverable_export", ["deliverable_id"])
    op.create_index("ix_deliverable_export_snapshot_hash", "deliverable_export", ["snapshot_hash"])
    op.create_index("ix_deliverable_export_requested_by_user_id", "deliverable_export", ["requested_by_user_id"])


def downgrade() -> None:
    op.drop_index("ix_deliverable_export_requested_by_user_id", table_name="deliverable_export")
    op.drop_index("ix_deliverable_export_snapshot_hash", table_name="deliverable_export")
    op.drop_index("ix_deliverable_export_deliverable_id", table_name="deliverable_export")
    op.drop_index("ix_deliverable_export_project_id", table_name="deliverable_export")
    op.drop_table("deliverable_export")
