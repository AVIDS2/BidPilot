"""add durable evidence sets and citation provenance

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-07-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evidence_set",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("execution_run_id", sa.String(length=36), nullable=False),
        sa.Column("section_key", sa.String(length=100), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("retrieval_profile_id", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="ready"),
        sa.Column("degraded_reasons_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("rejected_reasons_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column(
            "unmet_requirement_ids_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["execution_run_id"], ["execution_run.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_run_id", "section_key", name="uq_evidence_set_run_section"),
    )
    op.create_index("ix_evidence_set_project_id", "evidence_set", ["project_id"])
    op.create_index("ix_evidence_set_execution_run_id", "evidence_set", ["execution_run_id"])
    op.create_index(
        "ix_evidence_set_project_section",
        "evidence_set",
        ["project_id", "section_key"],
    )

    op.create_table(
        "evidence_set_item",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("evidence_set_id", sa.String(length=36), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_id", sa.String(length=36), nullable=False),
        sa.Column("source_document_version", sa.Integer(), nullable=False),
        sa.Column("source_document_checksum", sa.String(length=64), nullable=False),
        sa.Column("locator_json", sa.JSON(), nullable=False),
        sa.Column("quote_text", sa.Text(), nullable=False),
        sa.Column("retrieval_rank", sa.Integer(), nullable=False),
        sa.Column("retrieval_score", sa.Float(), nullable=False),
        sa.Column("retrieval_methods_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("selected_reason", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["evidence_set_id"], ["evidence_set.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_document_id"],
            ["source_document.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["chunk_id"], ["knowledge_chunk.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evidence_set_id", "chunk_id", name="uq_evidence_set_item_chunk"),
    )
    op.create_index("ix_evidence_set_item_evidence_set_id", "evidence_set_item", ["evidence_set_id"])

    op.add_column(
        "evidence",
        sa.Column("evidence_set_item_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_evidence_evidence_set_item_id",
        "evidence",
        "evidence_set_item",
        ["evidence_set_item_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_evidence_evidence_set_item_id", "evidence", ["evidence_set_item_id"])

    op.add_column(
        "section_version",
        sa.Column("evidence_set_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_section_version_evidence_set_id",
        "section_version",
        "evidence_set",
        ["evidence_set_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_section_version_evidence_set_id", "section_version", ["evidence_set_id"])


def downgrade() -> None:
    op.drop_index("ix_section_version_evidence_set_id", table_name="section_version")
    op.drop_constraint("fk_section_version_evidence_set_id", "section_version", type_="foreignkey")
    op.drop_column("section_version", "evidence_set_id")

    op.drop_index("ix_evidence_evidence_set_item_id", table_name="evidence")
    op.drop_constraint("fk_evidence_evidence_set_item_id", "evidence", type_="foreignkey")
    op.drop_column("evidence", "evidence_set_item_id")

    op.drop_index("ix_evidence_set_item_evidence_set_id", table_name="evidence_set_item")
    op.drop_table("evidence_set_item")

    op.drop_index("ix_evidence_set_project_section", table_name="evidence_set")
    op.drop_index("ix_evidence_set_execution_run_id", table_name="evidence_set")
    op.drop_index("ix_evidence_set_project_id", table_name="evidence_set")
    op.drop_table("evidence_set")
