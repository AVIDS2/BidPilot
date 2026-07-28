"""pin reviewed section versions to immutable export snapshots

Revision ID: b1c2d3e4f5a6
Revises: b0c1d2e3f4a5
Create Date: 2026-07-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "b0c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _foreign_keys(table_name: str) -> set[str]:
    return {
        foreign_key["name"]
        for foreign_key in sa.inspect(op.get_bind()).get_foreign_keys(table_name)
        if foreign_key.get("name")
    }


def _indexes(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def upgrade() -> None:
    # Existing approved rows are deliberately not backfilled: their historical
    # section status cannot prove which mutable body was actually approved.
    if "approved_version_id" not in _columns("deliverable_section"):
        op.add_column(
            "deliverable_section",
            sa.Column("approved_version_id", sa.String(length=36), nullable=True),
        )
    if "fk_deliverable_section_approved_version" not in _foreign_keys("deliverable_section"):
        op.create_foreign_key(
            "fk_deliverable_section_approved_version",
            "deliverable_section",
            "section_version",
            ["approved_version_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if "ix_deliverable_section_approved_version" not in _indexes("deliverable_section"):
        op.create_index(
            "ix_deliverable_section_approved_version",
            "deliverable_section",
            ["approved_version_id"],
        )

    if "section_version_id" not in _columns("review_thread"):
        op.add_column(
            "review_thread",
            sa.Column("section_version_id", sa.String(length=36), nullable=True),
        )
    if "fk_review_thread_section_version" not in _foreign_keys("review_thread"):
        op.create_foreign_key(
            "fk_review_thread_section_version",
            "review_thread",
            "section_version",
            ["section_version_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if "ix_review_thread_section_version" not in _indexes("review_thread"):
        op.create_index(
            "ix_review_thread_section_version",
            "review_thread",
            ["section_version_id"],
        )


def downgrade() -> None:
    if "ix_review_thread_section_version" in _indexes("review_thread"):
        op.drop_index("ix_review_thread_section_version", table_name="review_thread")
    if "fk_review_thread_section_version" in _foreign_keys("review_thread"):
        op.drop_constraint("fk_review_thread_section_version", "review_thread", type_="foreignkey")
    if "section_version_id" in _columns("review_thread"):
        op.drop_column("review_thread", "section_version_id")

    if "ix_deliverable_section_approved_version" in _indexes("deliverable_section"):
        op.drop_index("ix_deliverable_section_approved_version", table_name="deliverable_section")
    if "fk_deliverable_section_approved_version" in _foreign_keys("deliverable_section"):
        op.drop_constraint("fk_deliverable_section_approved_version", "deliverable_section", type_="foreignkey")
    if "approved_version_id" in _columns("deliverable_section"):
        op.drop_column("deliverable_section", "approved_version_id")
