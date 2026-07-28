"""add runtime event lineage metadata

Revision ID: b0c1d2e3f4a5
Revises: ad3e4f5b6c7d
Create Date: 2026-07-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b0c1d2e3f4a5"
down_revision: Union[str, Sequence[str], None] = "ad3e4f5b6c7d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if "parent_event_id" not in {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("runtime_event")
    }:
        op.add_column(
            "runtime_event",
            sa.Column("parent_event_id", sa.String(length=36), nullable=True),
        )
    op.alter_column(
        "runtime_event",
        "schema_version",
        existing_type=sa.String(length=20),
        server_default="1.1",
    )


def downgrade() -> None:
    op.alter_column(
        "runtime_event",
        "schema_version",
        existing_type=sa.String(length=20),
        server_default="1.0",
    )
    op.drop_column("runtime_event", "parent_event_id")
