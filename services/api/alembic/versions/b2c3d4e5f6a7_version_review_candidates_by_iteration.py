"""version review candidates by LangGraph iteration

Revision ID: b2c3d4e5f6a7
Revises: b1c2d3e4f5a6
Create Date: 2026-07-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _unique_constraints(table_name: str) -> set[str]:
    return {
        constraint["name"]
        for constraint in sa.inspect(op.get_bind()).get_unique_constraints(table_name)
        if constraint.get("name")
    }


def upgrade() -> None:
    if "generation_iteration" not in _columns("section_version"):
        op.add_column(
            "section_version",
            sa.Column(
                "generation_iteration",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )
    # Earlier retry handling could create more than one version for a single
    # run. Give existing rows deterministic iteration values before enforcing
    # the new idempotency constraint, ordered by their already-visible version.
    op.execute(
        """
        WITH ranked_versions AS (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY deliverable_section_id, generation_run_id
                    ORDER BY version_number ASC, id ASC
                ) - 1 AS iteration
            FROM section_version
            WHERE generation_run_id IS NOT NULL
        )
        UPDATE section_version AS version
        SET generation_iteration = ranked_versions.iteration
        FROM ranked_versions
        WHERE version.id = ranked_versions.id
        """
    )
    if "uq_section_version_run_iteration" not in _unique_constraints("section_version"):
        op.create_unique_constraint(
            "uq_section_version_run_iteration",
            "section_version",
            ["deliverable_section_id", "generation_run_id", "generation_iteration"],
        )


def downgrade() -> None:
    if "uq_section_version_run_iteration" in _unique_constraints("section_version"):
        op.drop_constraint(
            "uq_section_version_run_iteration",
            "section_version",
            type_="unique",
        )
    if "generation_iteration" in _columns("section_version"):
        op.drop_column("section_version", "generation_iteration")
