"""make requirement extraction provenance and coverage defaults durable

Revision ID: d5e6f7a8b9c0
Revises: c3d4e5f6a7b8
Create Date: 2026-07-27
"""

from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    if "extraction_key" not in _columns("requirement_item"):
        op.add_column(
            "requirement_item",
            sa.Column("extraction_key", sa.String(length=64), nullable=True),
        )

    # Legacy rows predate the explicit lifecycle. They have not yet been
    # triaged, regardless of their old UI-oriented draft/open value.
    op.execute(
        "UPDATE requirement_item SET status = 'untriaged' "
        "WHERE status IN ('draft', 'open')"
    )
    if bind.dialect.name != "sqlite":
        op.alter_column(
            "requirement_item",
            "status",
            existing_type=sa.String(length=30),
            server_default="untriaged",
        )

    if "uq_requirement_item_project_extraction_key" not in _indexes("requirement_item"):
        op.create_index(
            "uq_requirement_item_project_extraction_key",
            "requirement_item",
            ["project_id", "extraction_key"],
            unique=True,
        )

    missing_profile_ids = bind.execute(
        sa.text(
            """
            SELECT requirement.id
            FROM requirement_item AS requirement
            LEFT JOIN bid_requirement_profile AS profile
              ON profile.requirement_id = requirement.id
            WHERE profile.id IS NULL
            """
        )
    ).scalars()
    for requirement_id in missing_profile_ids:
        bind.execute(
            sa.text(
                """
                INSERT INTO bid_requirement_profile (
                    id,
                    requirement_id,
                    bid_category,
                    is_mandatory,
                    risk_level,
                    coverage_status,
                    evidence_status
                ) VALUES (
                    :id,
                    :requirement_id,
                    'technical',
                    :is_mandatory,
                    'normal',
                    'uncovered',
                    'missing'
                )
                """
            ),
            {
                "id": str(uuid4()),
                "requirement_id": requirement_id,
                "is_mandatory": False,
            },
        )


def downgrade() -> None:
    if "uq_requirement_item_project_extraction_key" in _indexes("requirement_item"):
        op.drop_index(
            "uq_requirement_item_project_extraction_key",
            table_name="requirement_item",
        )
    if "extraction_key" in _columns("requirement_item"):
        op.drop_column("requirement_item", "extraction_key")
