"""add durable assistant attachment staging

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-07-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assistant_attachment",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("bundle_id", sa.String(length=36), nullable=True),
        sa.Column("document_id", sa.String(length=36), nullable=True),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("extraction_status", sa.String(length=30), nullable=False),
        sa.Column("extracted_text", sa.Text(), server_default="", nullable=False),
        sa.Column("extraction_error", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("attached_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["bundle_id"], ["bundle.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["source_document.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["org_id"], ["organization.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assistant_attachment_user_id", "assistant_attachment", ["user_id"])
    op.create_index("ix_assistant_attachment_org_id", "assistant_attachment", ["org_id"])
    op.create_index("ix_assistant_attachment_project_id", "assistant_attachment", ["project_id"])
    op.create_index("ix_assistant_attachment_bundle_id", "assistant_attachment", ["bundle_id"])
    op.create_index("ix_assistant_attachment_document_id", "assistant_attachment", ["document_id"])
    op.create_index("ix_assistant_attachment_status", "assistant_attachment", ["status"])
    op.create_index("ix_assistant_attachment_expires_at", "assistant_attachment", ["expires_at"])
    op.create_index(
        "ix_assistant_attachment_owner_status_expiry",
        "assistant_attachment",
        ["user_id", "org_id", "status", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_assistant_attachment_owner_status_expiry", table_name="assistant_attachment")
    op.drop_index("ix_assistant_attachment_expires_at", table_name="assistant_attachment")
    op.drop_index("ix_assistant_attachment_status", table_name="assistant_attachment")
    op.drop_index("ix_assistant_attachment_document_id", table_name="assistant_attachment")
    op.drop_index("ix_assistant_attachment_bundle_id", table_name="assistant_attachment")
    op.drop_index("ix_assistant_attachment_project_id", table_name="assistant_attachment")
    op.drop_index("ix_assistant_attachment_org_id", table_name="assistant_attachment")
    op.drop_index("ix_assistant_attachment_user_id", table_name="assistant_attachment")
    op.drop_table("assistant_attachment")
