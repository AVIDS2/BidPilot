"""add execution retry lineage

Revision ID: f1a2b3c4d5e6
Revises: e8f9a0b1c2d3
Create Date: 2026-07-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("execution_run") as batch_op:
        batch_op.add_column(sa.Column("parent_execution_run_id", sa.String(length=36), nullable=True))
        batch_op.add_column(
            sa.Column("attempt_number", sa.Integer(), nullable=False, server_default=sa.text("1"))
        )
        batch_op.create_foreign_key(
            "fk_execution_run_parent_execution_run",
            "execution_run",
            ["parent_execution_run_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_unique_constraint(
            "uq_execution_run_parent_attempt",
            ["parent_execution_run_id", "attempt_number"],
        )


def downgrade() -> None:
    with op.batch_alter_table("execution_run") as batch_op:
        batch_op.drop_constraint("uq_execution_run_parent_attempt", type_="unique")
        batch_op.drop_constraint("fk_execution_run_parent_execution_run", type_="foreignkey")
        batch_op.drop_column("attempt_number")
        batch_op.drop_column("parent_execution_run_id")
