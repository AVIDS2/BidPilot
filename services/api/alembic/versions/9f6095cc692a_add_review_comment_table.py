"""add_review_comment_table

Revision ID: 9f6095cc692a
Revises: 4ed843518e73
Create Date: 2026-04-21 23:05:42.112092

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f6095cc692a'
down_revision: Union[str, Sequence[str], None] = '4ed843518e73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('review_comment',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('review_thread_id', sa.String(length=36), nullable=False),
    sa.Column('author_type', sa.String(length=30), nullable=False),
    sa.Column('author_id', sa.String(length=36), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['review_thread_id'], ['review_thread.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('review_comment')
