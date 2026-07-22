"""add Retrieval 2 profile fields and hybrid-search indexes

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-07-17

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add profile provenance and the PostgreSQL indexes Retrieval 2 requires."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.add_column(
        "knowledge_chunk",
        sa.Column("retrieval_text", sa.Text(), nullable=False, server_default=sa.text("''")),
    )
    op.add_column("knowledge_chunk", sa.Column("embedding_profile", sa.String(length=500), nullable=True))
    op.add_column(
        "knowledge_chunk",
        sa.Column(
            "embedding_status",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
    )
    op.add_column("knowledge_chunk", sa.Column("embedding_updated_at", sa.DateTime(), nullable=True))
    op.add_column("knowledge_chunk", sa.Column("embedding_error_code", sa.String(length=100), nullable=True))

    # Existing vector rows predate retrieval profiles. They remain sparse-searchable
    # but must be reindexed before participating in a profile-scoped dense query.
    op.execute(
        """
        UPDATE knowledge_chunk
        SET retrieval_text = content,
            embedding_status = CASE
                WHEN embedding IS NULL THEN 'pending'
                ELSE 'stale'
            END
        WHERE retrieval_text = ''
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunk_project_id "
        "ON knowledge_chunk (project_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunk_project_embedding_profile "
        "ON knowledge_chunk (project_id, embedding_profile)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunk_retrieval_text_fts "
        "ON knowledge_chunk USING gin (to_tsvector('simple', retrieval_text))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunk_content_trgm "
        "ON knowledge_chunk USING gin (content gin_trgm_ops)"
    )
    # Migration 27bbad823c47 accidentally removed this original index. Recreate it
    # in a new additive revision rather than rewriting migration history.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunk_embedding_hnsw "
        "ON knowledge_chunk USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64) "
        "WHERE embedding IS NOT NULL"
    )


def downgrade() -> None:
    """Remove Retrieval 2 schema additions without removing shared extensions."""
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunk_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunk_content_trgm")
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunk_retrieval_text_fts")
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunk_project_embedding_profile")
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunk_project_id")
    op.drop_column("knowledge_chunk", "embedding_error_code")
    op.drop_column("knowledge_chunk", "embedding_updated_at")
    op.drop_column("knowledge_chunk", "embedding_status")
    op.drop_column("knowledge_chunk", "embedding_profile")
    op.drop_column("knowledge_chunk", "retrieval_text")
