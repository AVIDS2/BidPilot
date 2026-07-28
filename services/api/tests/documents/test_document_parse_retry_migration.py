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
        / "fd2e3f4a5b6c_add_document_parse_retry_budget.py"
    )
    spec = importlib.util.spec_from_file_location("document_parse_retry_budget_migration", migration_path)
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


def test_document_parse_retry_budget_migration_is_additive_and_reversible() -> None:
    engine = create_engine("sqlite://")
    metadata = sa.MetaData()
    source_document = sa.Table(
        "source_document",
        metadata,
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("parse_status", sa.String(length=30), nullable=False),
    )
    metadata.create_all(engine)
    migration = _load_migration_module()

    with engine.begin() as connection:
        connection.execute(sa.insert(source_document), [{"id": "legacy", "parse_status": "failed"}])
        _run_migration(connection, migration, "upgrade")

        columns = {column["name"] for column in sa.inspect(connection).get_columns("source_document")}
        assert "parse_attempt_count" in columns
        assert connection.execute(
            sa.text("SELECT parse_attempt_count FROM source_document WHERE id = 'legacy'")
        ).scalar_one() == 0

        _run_migration(connection, migration, "downgrade")
        columns = {column["name"] for column in sa.inspect(connection).get_columns("source_document")}
        assert "parse_attempt_count" not in columns
