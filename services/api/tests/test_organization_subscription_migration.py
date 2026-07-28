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
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "e5f6a7b8c9d0_add_organization_subscriptions.py"
    )
    spec = importlib.util.spec_from_file_location("organization_subscription_migration", migration_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_upgrade(connection: sa.Connection, migration) -> None:
    previous_proxy = getattr(op, "_proxy", None)
    op._proxy = Operations(MigrationContext.configure(connection))
    try:
        migration.upgrade()
    finally:
        if previous_proxy is None:
            del op._proxy
        else:
            op._proxy = previous_proxy


def _legacy_subscription_schema(engine) -> None:
    metadata = sa.MetaData()
    sa.Table("organization", metadata, sa.Column("id", sa.String(length=36), primary_key=True))
    sa.Table("user", metadata, sa.Column("id", sa.String(length=36), primary_key=True))
    sa.Table(
        "organization_subscription",
        metadata,
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("plan", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("seat_limit", sa.Integer(), nullable=False),
        sa.Column("billable_seat_count", sa.Integer(), nullable=False),
        sa.Column("billing_owner_user_id", sa.String(length=36), nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=255)),
        sa.Column("stripe_subscription_id", sa.String(length=255)),
        sa.Column("stripe_subscription_item_id", sa.String(length=255)),
        sa.Column("stripe_state_event_created_at", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    metadata.create_all(engine)


def test_subscription_migration_adopts_a_complete_legacy_table() -> None:
    engine = create_engine("sqlite://")
    _legacy_subscription_schema(engine)
    migration = _load_migration_module()

    with engine.begin() as connection:
        _run_upgrade(connection, migration)

        indexes = {index["name"] for index in sa.inspect(connection).get_indexes("organization_subscription")}
        assert "ix_organization_subscription_billing_owner" in indexes


def test_subscription_migration_rejects_an_incomplete_legacy_table() -> None:
    engine = create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("organization_subscription", metadata, sa.Column("id", sa.String(length=36), primary_key=True))
    metadata.create_all(engine)
    migration = _load_migration_module()

    with engine.begin() as connection:
        try:
            _run_upgrade(connection, migration)
        except RuntimeError as error:
            assert "missing required columns" in str(error)
        else:
            raise AssertionError("incomplete legacy table must not be silently accepted")
