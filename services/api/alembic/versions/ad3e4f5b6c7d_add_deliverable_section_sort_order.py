"""add deliverable section sort order for outline editor

Revision ID: ad3e4f5b6c7d
Revises: ac2d3e4f5b6c
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ad3e4f5b6c7d"
down_revision: Union[str, Sequence[str], None] = "ac2d3e4f5b6c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "deliverable_section",
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_deliverable_section_deliverable_sort",
        "deliverable_section",
        ["deliverable_id", "sort_order"],
    )


def downgrade() -> None:
    op.drop_index("ix_deliverable_section_deliverable_sort", table_name="deliverable_section")
    op.drop_column("deliverable_section", "sort_order")
