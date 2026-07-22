import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine

from app.db import Base
from app.models import Organization, Project, ProjectMember, User


def _load_migration_module():
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "d7e8f9a0b1c2_add_project_member_access.py"
    )
    spec = importlib.util.spec_from_file_location("project_member_access_migration", migration_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_migration(connection: sa.Connection, migration, action: str) -> None:
    previous_proxy = getattr(op, "_proxy", None)
    op._proxy = Operations(MigrationContext.configure(connection))
    try:
        getattr(migration, action)()
    finally:
        if previous_proxy is None:
            del op._proxy
        else:
            op._proxy = previous_proxy


def test_project_member_migration_backfills_legacy_access_and_downgrades() -> None:
    engine = create_engine("sqlite://")
    legacy_tables = [Organization.__table__, User.__table__, Project.__table__]
    Base.metadata.create_all(engine, tables=legacy_tables)
    migration = _load_migration_module()

    with engine.begin() as connection:
        connection.execute(
            sa.insert(Organization),
            [
                {"id": "org-with-users", "slug": "with-users", "name": "With Users"},
                {"id": "org-empty", "slug": "empty", "name": "Empty"},
            ],
        )
        connection.execute(
            sa.insert(User),
            [
                {
                    "id": "user-admin",
                    "org_id": "org-with-users",
                    "email": "admin@example.test",
                    "display_name": "Admin",
                    "role": "admin",
                    "disabled": False,
                    "email_verified": True,
                    "password_hash": "test-only",
                },
                {
                    "id": "user-member",
                    "org_id": "org-with-users",
                    "email": "member@example.test",
                    "display_name": "Member",
                    "role": "member",
                    "disabled": False,
                    "email_verified": True,
                    "password_hash": "test-only",
                },
                {
                    "id": "user-disabled",
                    "org_id": "org-with-users",
                    "email": "disabled@example.test",
                    "display_name": "Disabled",
                    "role": "member",
                    "disabled": True,
                    "email_verified": True,
                    "password_hash": "test-only",
                },
            ],
        )
        connection.execute(
            sa.insert(Project),
            [
                {
                    "id": "project-with-users",
                    "org_id": "org-with-users",
                    "slug": "with-users",
                    "name": "With Users",
                    "scenario_package": "bidpilot",
                    "status": "active",
                },
                {
                    "id": "project-empty",
                    "org_id": "org-empty",
                    "slug": "empty",
                    "name": "Empty",
                    "scenario_package": "bidpilot",
                    "status": "active",
                },
            ],
        )

        _run_migration(connection, migration, "upgrade")

        memberships = connection.execute(
            sa.select(ProjectMember.project_id, ProjectMember.user_id, ProjectMember.role).order_by(
                ProjectMember.user_id
            )
        ).mappings().all()
        assert [dict(row) for row in memberships] == [
            {"project_id": "project-with-users", "user_id": "user-admin", "role": "owner"},
            {"project_id": "project-with-users", "user_id": "user-member", "role": "contributor"},
        ]

        _run_migration(connection, migration, "downgrade")
        table_names = sa.inspect(connection).get_table_names()
        assert "project_member" not in table_names
