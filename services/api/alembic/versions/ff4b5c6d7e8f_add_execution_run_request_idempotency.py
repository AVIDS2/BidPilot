"""add execution run request idempotency

Revision ID: ff4b5c6d7e8f
Revises: fe3a4b5c6d7e
Create Date: 2026-08-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ff4b5c6d7e8f"
down_revision: Union[str, Sequence[str], None] = "fe3a4b5c6d7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _unique_constraints(table_name: str) -> set[str]:
    return {
        constraint["name"]
        for constraint in sa.inspect(op.get_bind()).get_unique_constraints(table_name)
        if constraint.get("name")
    }


def upgrade() -> None:
    columns = _columns("execution_run")
    if "requested_by_user_id" not in columns:
        op.add_column(
            "execution_run",
            sa.Column("requested_by_user_id", sa.String(length=36), nullable=True),
        )
    if "client_request_id" not in columns:
        op.add_column(
            "execution_run",
            sa.Column("client_request_id", sa.String(length=128), nullable=True),
        )

    indexes = _indexes("execution_run")
    if "ix_execution_run_request_id" not in indexes:
        op.create_index(
            "ix_execution_run_request_id",
            "execution_run",
            ["requested_by_user_id", "client_request_id"],
        )

    constraints = _unique_constraints("execution_run")
    if "uq_execution_run_user_client_request" not in constraints:
        op.create_unique_constraint(
            "uq_execution_run_user_client_request",
            "execution_run",
            ["requested_by_user_id", "client_request_id"],
        )


def downgrade() -> None:
    constraints = _unique_constraints("execution_run")
    if "uq_execution_run_user_client_request" in constraints:
        op.drop_constraint("uq_execution_run_user_client_request", "execution_run", type_="unique")
    indexes = _indexes("execution_run")
    if "ix_execution_run_request_id" in indexes:
        op.drop_index("ix_execution_run_request_id", table_name="execution_run")
    columns = _columns("execution_run")
    if "client_request_id" in columns:
        op.drop_column("execution_run", "client_request_id")
    if "requested_by_user_id" in columns:
        op.drop_column("execution_run", "requested_by_user_id")
