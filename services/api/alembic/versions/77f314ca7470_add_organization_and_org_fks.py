"""add_organization_and_org_fks

Revision ID: 77f314ca7470
Revises: cc12fa586336
Create Date: 2026-05-16 21:43:55.133933

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '77f314ca7470'
down_revision: Union[str, Sequence[str], None] = 'cc12fa586336'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create organization table
    op.create_table('organization',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('slug', sa.String(length=100), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )

    # Insert default organization with stable UUID
    default_org_id = "00000000-0000-0000-0000-000000000001"
    op.execute(
        f"INSERT INTO organization (id, slug, name) VALUES ('{default_org_id}', 'default', 'Default Organization')"
    )

    # Add nullable org_id columns first
    op.add_column('project', sa.Column('org_id', sa.String(length=36), nullable=True))
    op.add_column('user', sa.Column('org_id', sa.String(length=36), nullable=True))

    # Populate existing rows with default org
    op.execute(f"UPDATE project SET org_id = '{default_org_id}'")
    op.execute(f"UPDATE \"user\" SET org_id = '{default_org_id}'")

    # Make columns NOT NULL
    op.alter_column('project', 'org_id', nullable=False)
    op.alter_column('user', 'org_id', nullable=False)

    # Add foreign keys
    op.create_foreign_key(None, 'project', 'organization', ['org_id'], ['id'])
    op.create_foreign_key(None, 'user', 'organization', ['org_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(None, 'user', type_='foreignkey')
    op.drop_column('user', 'org_id')
    op.drop_constraint(None, 'project', type_='foreignkey')
    op.drop_column('project', 'org_id')
    op.drop_table('organization')
