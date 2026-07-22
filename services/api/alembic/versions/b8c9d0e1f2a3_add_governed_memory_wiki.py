"""add governed memory ledger and Bid Wiki projection

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector


revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add additive, evidence-oriented memory tables without touching existing data."""
    op.create_table(
        "memory_record",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("owner_user_id", sa.String(length=36), nullable=True),
        sa.Column("scope", sa.String(length=30), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'proposed'")),
        sa.Column("privacy_classification", sa.String(length=30), nullable=False, server_default=sa.text("'internal'")),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("structured_data_json", sa.JSON(), nullable=True),
        sa.Column("content_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("retrieval_text", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("embedding_profile", sa.String(length=500), nullable=True),
        sa.Column("embedding_status", sa.String(length=30), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("embedding_updated_at", sa.DateTime(), nullable=True),
        sa.Column("embedding_error_code", sa.String(length=100), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("origin", sa.String(length=30), nullable=False),
        sa.Column("created_by_actor_type", sa.String(length=30), nullable=False),
        sa.Column("created_by_actor_id", sa.String(length=36), nullable=True),
        sa.Column("supersedes_id", sa.String(length=36), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organization.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["memory_record.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_memory_record_org_scope_status_updated",
        "memory_record",
        ["org_id", "scope", "status", "updated_at"],
    )
    op.create_index(
        "ix_memory_record_project_status_updated",
        "memory_record",
        ["project_id", "status", "updated_at"],
    )
    op.create_index(
        "ix_memory_record_owner_status_updated",
        "memory_record",
        ["owner_user_id", "status", "updated_at"],
    )
    op.create_index(
        "ix_memory_record_project_embedding_profile",
        "memory_record",
        ["project_id", "embedding_profile"],
    )
    op.execute(
        "CREATE INDEX ix_memory_record_retrieval_text_fts "
        "ON memory_record USING gin (to_tsvector('simple', retrieval_text))"
    )
    op.execute(
        "CREATE INDEX ix_memory_record_embedding_hnsw "
        "ON memory_record USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64) "
        "WHERE embedding IS NOT NULL AND status = 'active' AND deleted_at IS NULL"
    )

    op.create_table(
        "memory_evidence_link",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("memory_record_id", sa.String(length=36), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.String(length=80), nullable=False),
        sa.Column("evidence_role", sa.String(length=30), nullable=False, server_default=sa.text("'supports'")),
        sa.Column("label", sa.String(length=500), nullable=False),
        sa.Column("locator_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["memory_record_id"], ["memory_record.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "memory_record_id",
            "source_type",
            "source_id",
            "evidence_role",
            name="uq_memory_evidence_link_source",
        ),
    )
    op.create_index("ix_memory_evidence_link_source", "memory_evidence_link", ["source_type", "source_id"])

    op.create_table(
        "memory_entity",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("memory_record_id", sa.String(length=36), nullable=False),
        sa.Column("canonical_name", sa.String(length=240), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("aliases_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organization.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["memory_record_id"], ["memory_record.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_memory_entity_project_type_name",
        "memory_entity",
        ["project_id", "entity_type", "canonical_name"],
    )
    op.create_index("ix_memory_entity_org_status", "memory_entity", ["org_id", "status"])

    op.create_table(
        "memory_relation",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("memory_record_id", sa.String(length=36), nullable=False),
        sa.Column("subject_entity_id", sa.String(length=36), nullable=False),
        sa.Column("object_entity_id", sa.String(length=36), nullable=False),
        sa.Column("predicate", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organization.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["memory_record_id"], ["memory_record.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_entity_id"], ["memory_entity.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["object_entity_id"], ["memory_entity.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "memory_record_id",
            "subject_entity_id",
            "object_entity_id",
            "predicate",
            name="uq_memory_relation_record_edge",
        ),
    )
    op.create_index("ix_memory_relation_project_status", "memory_relation", ["project_id", "status"])
    op.create_index("ix_memory_relation_subject", "memory_relation", ["subject_entity_id", "status"])
    op.create_index("ix_memory_relation_object", "memory_relation", ["object_entity_id", "status"])

    op.create_table(
        "memory_compilation_run",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("bundle_id", sa.String(length=36), nullable=True),
        sa.Column("initiated_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("input_source_ids_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("input_memory_ids_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("embedding_profile", sa.String(length=500), nullable=True),
        sa.Column("policy_version", sa.String(length=100), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organization.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["bundle_id"], ["bundle.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["initiated_by_user_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_memory_compilation_run_project_status_created",
        "memory_compilation_run",
        ["project_id", "status", "created_at"],
    )
    op.create_index("ix_memory_compilation_run_org_created", "memory_compilation_run", ["org_id", "created_at"])


def downgrade() -> None:
    """Remove only the governed-memory tables and their dedicated indexes."""
    op.drop_index("ix_memory_compilation_run_org_created", table_name="memory_compilation_run")
    op.drop_index("ix_memory_compilation_run_project_status_created", table_name="memory_compilation_run")
    op.drop_table("memory_compilation_run")
    op.drop_index("ix_memory_relation_object", table_name="memory_relation")
    op.drop_index("ix_memory_relation_subject", table_name="memory_relation")
    op.drop_index("ix_memory_relation_project_status", table_name="memory_relation")
    op.drop_table("memory_relation")
    op.drop_index("ix_memory_entity_org_status", table_name="memory_entity")
    op.drop_index("ix_memory_entity_project_type_name", table_name="memory_entity")
    op.drop_table("memory_entity")
    op.drop_index("ix_memory_evidence_link_source", table_name="memory_evidence_link")
    op.drop_table("memory_evidence_link")
    op.execute("DROP INDEX IF EXISTS ix_memory_record_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_memory_record_retrieval_text_fts")
    op.drop_index("ix_memory_record_project_embedding_profile", table_name="memory_record")
    op.drop_index("ix_memory_record_owner_status_updated", table_name="memory_record")
    op.drop_index("ix_memory_record_project_status_updated", table_name="memory_record")
    op.drop_index("ix_memory_record_org_scope_status_updated", table_name="memory_record")
    op.drop_table("memory_record")
