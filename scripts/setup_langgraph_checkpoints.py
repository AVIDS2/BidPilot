"""Initialize LangGraph Postgres checkpoint tables as a deployment step."""

from __future__ import annotations

import os

from langgraph.checkpoint.postgres import PostgresSaver


def checkpoint_connection_url(database_url: str) -> str:
    """Translate the SQLAlchemy psycopg URL without logging its credential."""
    value = database_url.strip()
    if not value:
        raise RuntimeError("DOCPILOT_DATABASE_URL is required to initialize LangGraph checkpoints")
    if value.startswith("postgresql+psycopg://"):
        return value.replace("postgresql+psycopg://", "postgresql://", 1)
    return value


def main() -> int:
    database_url = checkpoint_connection_url(os.environ.get("DOCPILOT_DATABASE_URL", ""))
    with PostgresSaver.from_conn_string(database_url) as checkpointer:
        checkpointer.setup()
    print("LangGraph checkpoint tables are ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
