from app.db import Base


def test_db_module_reexports_metadata_base() -> None:
    """Alembic and services share the canonical declarative metadata."""
    assert Base.metadata is not None
