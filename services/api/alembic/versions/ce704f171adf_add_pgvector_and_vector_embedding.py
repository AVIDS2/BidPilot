"""add pgvector and vector embedding

Revision ID: ce704f171adf
Revises: 2f358b58a579
Create Date: 2026-04-21 20:35:23.771120

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy.vector


# revision identifiers, used by Alembic.
revision: str = 'ce704f171adf'
down_revision: Union[str, Sequence[str], None] = '2f358b58a579'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.execute(
        "ALTER TABLE knowledge_chunk ALTER COLUMN embedding TYPE VECTOR(1536) USING embedding::vector(1536)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('knowledge_chunk', 'embedding',
               existing_type=pgvector.sqlalchemy.vector.VECTOR(dim=1536),
               type_=sa.VARCHAR(length=50000),
               existing_nullable=True)
