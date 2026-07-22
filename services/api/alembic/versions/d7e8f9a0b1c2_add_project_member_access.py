"""add project member access

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-07-14
"""

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, Sequence[str], None] = "c6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_member",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(length=36),
            sa.ForeignKey("project.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(length=30),
            nullable=False,
            server_default="contributor",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_member_project_user"),
    )
    op.create_index("ix_project_member_project_id", "project_member", ["project_id"])
    op.create_index("ix_project_member_user_id", "project_member", ["user_id"])

    bind = op.get_bind()
    projects = bind.execute(sa.text("SELECT id, org_id FROM project")).mappings().all()
    users = bind.execute(
        sa.text('SELECT id, org_id, role FROM "user" WHERE disabled = false')
    ).mappings().all()
    users_by_org: dict[str, list[dict[str, str]]] = {}
    for user in users:
        users_by_org.setdefault(user["org_id"], []).append(dict(user))

    project_member = sa.table(
        "project_member",
        sa.column("id", sa.String),
        sa.column("project_id", sa.String),
        sa.column("user_id", sa.String),
        sa.column("role", sa.String),
    )
    inherited_memberships = [
        {
            "id": str(uuid.uuid4()),
            "project_id": project["id"],
            "user_id": user["id"],
            "role": "owner" if user["role"] == "admin" else "contributor",
        }
        for project in projects
        for user in users_by_org.get(project["org_id"], [])
    ]
    if inherited_memberships:
        bind.execute(project_member.insert(), inherited_memberships)


def downgrade() -> None:
    op.drop_index("ix_project_member_user_id", table_name="project_member")
    op.drop_index("ix_project_member_project_id", table_name="project_member")
    op.drop_table("project_member")
