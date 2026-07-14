"""add readiness pack

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-07-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c6d7e8f9a0b1"
down_revision: Union[str, Sequence[str], None] = "b5c6d7e8f9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "readiness_pack",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(length=36),
            sa.ForeignKey("project.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("formula_version", sa.String(length=30), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="generated"),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("xlsx_storage_key", sa.String(length=500), nullable=True),
        sa.Column("docx_storage_key", sa.String(length=500), nullable=True),
        sa.Column(
            "generated_by_user_id",
            sa.String(length=36),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "project_id",
            "version_number",
            name="uq_readiness_pack_project_version",
        ),
    )
    op.create_index("ix_readiness_pack_project_id", "readiness_pack", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_readiness_pack_project_id", table_name="readiness_pack")
    op.drop_table("readiness_pack")
