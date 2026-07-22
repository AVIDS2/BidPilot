from __future__ import annotations

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine


def _load_migration_module():
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "f1a2b3c4d5e6_add_execution_run_retry_lineage.py"
    )
    spec = importlib.util.spec_from_file_location("execution_retry_lineage_migration", migration_path)
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


def test_execution_retry_lineage_migration_is_additive_and_reversible() -> None:
    engine = create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("project", metadata, sa.Column("id", sa.String(length=36), primary_key=True))
    sa.Table(
        "execution_run",
        metadata,
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("project.id"), nullable=False),
        sa.Column("run_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
    )
    metadata.create_all(engine)
    migration = _load_migration_module()

    with engine.begin() as connection:
        _run_migration(connection, migration, "upgrade")

        inspector = sa.inspect(connection)
        assert {"parent_execution_run_id", "attempt_number"} <= {
            column["name"] for column in inspector.get_columns("execution_run")
        }
        assert ("parent_execution_run_id", "attempt_number") in {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("execution_run")
        }

        _run_migration(connection, migration, "downgrade")
        assert {"parent_execution_run_id", "attempt_number"}.isdisjoint(
            {column["name"] for column in sa.inspect(connection).get_columns("execution_run")}
        )
