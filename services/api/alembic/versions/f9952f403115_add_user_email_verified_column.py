"""add_user_email_verified_column

Revision ID: f9952f403115
Revises: 2e5dc6faa08e
Create Date: 2026-05-03 19:54:22.898951

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9952f403115'
down_revision: Union[str, Sequence[str], None] = '2e5dc6faa08e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('user', sa.Column('email_verified', sa.Boolean(), nullable=True))
    op.execute("UPDATE \"user\" SET email_verified = false WHERE email_verified IS NULL")
    op.alter_column('user', 'email_verified', nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('user', 'email_verified')
