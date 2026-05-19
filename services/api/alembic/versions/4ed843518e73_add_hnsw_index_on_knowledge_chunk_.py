"""add hnsw index on knowledge_chunk embedding

Revision ID: 4ed843518e73
Revises: ce704f171adf
Create Date: 2026-04-21 22:16:24.033843

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4ed843518e73'
down_revision: Union[str, Sequence[str], None] = 'ce704f171adf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunk_embedding_hnsw "
        "ON knowledge_chunk USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunk_embedding_hnsw")
