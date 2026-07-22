"""add durable organization memberships

Revision ID: d4e5f6a7b8c9
Revises: d3e4f5a6b7c8
Create Date: 2026-07-18
"""

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organization_membership",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(length=36),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=30), nullable=False, server_default="member"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("removed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("org_id", "user_id", name="uq_organization_membership_org_user"),
    )
    op.create_index(
        "ix_organization_membership_org_status",
        "organization_membership",
        ["org_id", "status"],
    )
    op.create_index(
        "ix_organization_membership_user_status",
        "organization_membership",
        ["user_id", "status"],
    )

    # Preserve every existing user's current workspace. The earliest enabled
    # account becomes its deterministic initial owner; no global admin role is
    # inferred as a customer billing role.
    bind = op.get_bind()
    users = bind.execute(
        sa.text(
            'SELECT id, org_id, disabled, created_at FROM "user" '
            "ORDER BY org_id, created_at, id"
        )
    ).mappings().all()
    membership = sa.table(
        "organization_membership",
        sa.column("id", sa.String),
        sa.column("org_id", sa.String),
        sa.column("user_id", sa.String),
        sa.column("role", sa.String),
        sa.column("status", sa.String),
    )
    owner_assigned: set[str] = set()
    rows: list[dict[str, str]] = []
    for user in users:
        active = not bool(user["disabled"])
        role = "member"
        if active and user["org_id"] not in owner_assigned:
            role = "owner"
            owner_assigned.add(user["org_id"])
        rows.append(
            {
                "id": str(uuid.uuid4()),
                "org_id": user["org_id"],
                "user_id": user["id"],
                "role": role,
                "status": "active" if active else "removed",
            }
        )
    if rows:
        bind.execute(membership.insert(), rows)


def downgrade() -> None:
    op.drop_index(
        "ix_organization_membership_user_status",
        table_name="organization_membership",
    )
    op.drop_index(
        "ix_organization_membership_org_status",
        table_name="organization_membership",
    )
    op.drop_table("organization_membership")
