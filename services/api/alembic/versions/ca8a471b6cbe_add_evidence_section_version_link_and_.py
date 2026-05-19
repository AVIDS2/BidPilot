"""add_evidence_section_version_link_and_deliverable_export_status

Revision ID: ca8a471b6cbe
Revises: 9f6095cc692a
Create Date: 2026-04-21 23:18:04.058649

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ca8a471b6cbe'
down_revision: Union[str, Sequence[str], None] = '9f6095cc692a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('deliverable', sa.Column('export_status', sa.String(length=30), nullable=False, server_default='not_exported'))
    op.add_column('deliverable', sa.Column('export_storage_key', sa.String(length=500), nullable=True))
    op.add_column('evidence', sa.Column('section_version_id', sa.String(length=36), nullable=True))
    op.alter_column('evidence', 'source_document_id',
               existing_type=sa.VARCHAR(length=36),
               nullable=True)
    op.create_foreign_key('fk_evidence_section_version_id', 'evidence', 'section_version', ['section_version_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_evidence_section_version_id', 'evidence', type_='foreignkey')
    op.alter_column('evidence', 'source_document_id',
               existing_type=sa.VARCHAR(length=36),
               nullable=False)
    op.drop_column('evidence', 'section_version_id')
    op.drop_column('deliverable', 'export_storage_key')
    op.drop_column('deliverable', 'export_status')
