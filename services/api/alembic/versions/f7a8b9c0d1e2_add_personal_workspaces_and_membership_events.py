"""add personal workspace classification and organization membership audit events

Revision ID: f7a8b9c0d1e2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    organization_columns = {column["name"] for column in inspector.get_columns("organization")}
    if "workspace_kind" not in organization_columns:
        op.add_column(
            "organization",
            sa.Column(
                "workspace_kind",
                sa.String(length=30),
                nullable=False,
                server_default="team",
            ),
        )

    if "ck_organization_workspace_kind" not in {
        constraint["name"] for constraint in sa.inspect(bind).get_check_constraints("organization")
    }:
        op.create_check_constraint(
            "ck_organization_workspace_kind",
            "organization",
            "workspace_kind IN ('personal', 'team')",
        )

    if not sa.inspect(bind).has_table("organization_membership_event"):
        op.create_table(
            "organization_membership_event",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("org_id", sa.String(length=36), nullable=False),
            sa.Column("membership_id", sa.String(length=36), nullable=True),
            sa.Column("actor_user_id", sa.String(length=36), nullable=True),
            sa.Column("target_user_id", sa.String(length=36), nullable=True),
            sa.Column("event_type", sa.String(length=100), nullable=False),
            sa.Column("payload_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["membership_id"], ["organization_membership.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["org_id"], ["organization.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["target_user_id"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    existing_indexes = {
        index["name"] for index in sa.inspect(bind).get_indexes("organization_membership_event")
    }
    if "ix_organization_membership_event_org_created" not in existing_indexes:
        op.create_index(
            "ix_organization_membership_event_org_created",
            "organization_membership_event",
            ["org_id", "created_at"],
        )
    if "ix_organization_membership_event_target_created" not in existing_indexes:
        op.create_index(
            "ix_organization_membership_event_target_created",
            "organization_membership_event",
            ["target_user_id", "created_at"],
        )


def downgrade() -> None:
    op.drop_index(
        "ix_organization_membership_event_target_created",
        table_name="organization_membership_event",
    )
    op.drop_index(
        "ix_organization_membership_event_org_created",
        table_name="organization_membership_event",
    )
    op.drop_table("organization_membership_event")
    op.drop_constraint("ck_organization_workspace_kind", "organization", type_="check")
    op.drop_column("organization", "workspace_kind")
