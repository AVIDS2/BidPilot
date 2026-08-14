"""bump runtime event schema default to 1.2

Revision ID: c26d7e8f9012
Revises: b15c6d7e8f90
Create Date: 2026-08-05
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c26d7e8f9012"
down_revision: Union[str, Sequence[str], None] = "b15c6d7e8f90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "runtime_event",
        "schema_version",
        existing_type=sa.String(length=20),
        server_default="1.2",
    )


def downgrade() -> None:
    op.alter_column(
        "runtime_event",
        "schema_version",
        existing_type=sa.String(length=20),
        server_default="1.1",
    )
