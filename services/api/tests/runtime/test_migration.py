from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine

from app.db import Base
from app.models import ChatConversation, ExecutionRun, Organization, Project, User


def _load_migration_module():
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "e8f9a0b1c2d3_add_runtime_control_plane.py"
    )
    spec = importlib.util.spec_from_file_location("runtime_control_plane_migration", migration_path)
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


def test_runtime_control_plane_migration_creates_idempotent_tables() -> None:
    engine = create_engine("sqlite://")
    legacy_tables = [
        Organization.__table__,
        User.__table__,
        Project.__table__,
        ExecutionRun.__table__,
        ChatConversation.__table__,
    ]
    Base.metadata.create_all(engine, tables=legacy_tables)
    migration = _load_migration_module()

    with engine.begin() as connection:
        _run_migration(connection, migration, "upgrade")

        inspector = sa.inspect(connection)
        assert {"runtime_run", "runtime_event", "runtime_action", "runtime_approval"} <= set(
            inspector.get_table_names()
        )
        assert {
            "trace_id",
            "idempotency_key",
            "policy_snapshot_json",
            "execution_run_id",
        } <= {column["name"] for column in inspector.get_columns("runtime_run")}
        assert {"run_id", "sequence", "event_type", "public_summary"} <= {
            column["name"] for column in inspector.get_columns("runtime_event")
        }
        assert ("run_id", "action_key") in {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("runtime_action")
        }
        assert ("action_id",) in {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("runtime_approval")
        }

        _run_migration(connection, migration, "downgrade")
        assert "runtime_run" not in sa.inspect(connection).get_table_names()
