"""add user personal memory preference

Revision ID: 07a8b9c0d1e2
Revises: 06f7a8b9c0d1
Create Date: 2026-09-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "07a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "06f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("user")}
    if "memory_enabled" in columns:
        return
    op.add_column(
        "user",
        sa.Column("memory_enabled", sa.Boolean(), nullable=True, server_default=sa.true()),
    )
    op.execute('UPDATE "user" SET memory_enabled = true WHERE memory_enabled IS NULL')
    op.alter_column("user", "memory_enabled", nullable=False, server_default=sa.true())


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("user")}
    if "memory_enabled" in columns:
        op.drop_column("user", "memory_enabled")
