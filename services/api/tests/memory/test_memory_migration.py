import pytest
from sqlalchemy import text

from app.db import SessionLocal


def test_governed_memory_schema_has_ledger_and_project_scoped_indexes() -> None:
    db = SessionLocal()
    try:
        if db.get_bind().dialect.name != "postgresql":
            pytest.skip("governed-memory indexes are PostgreSQL-specific")

        tables = set(
            db.execute(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name IN (
                        'memory_record',
                        'memory_event',
                        'memory_graph_review_decision',
                        'memory_evidence_link',
                        'memory_entity',
                        'memory_relation',
                        'memory_compilation_run'
                      )
                    """
                )
            ).scalars()
        )
        assert tables == {
            "memory_record",
            "memory_event",
            "memory_graph_review_decision",
            "memory_evidence_link",
            "memory_entity",
            "memory_relation",
            "memory_compilation_run",
        }

        columns = {
            row[0]
            for row in db.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'memory_record'
                    """
                )
            )
        }
        assert {
            "org_id",
            "project_id",
            "owner_user_id",
            "scope",
            "kind",
            "status",
            "retrieval_text",
            "embedding",
            "embedding_profile",
            "embedding_status",
            "supersedes_id",
            "expires_at",
        } <= columns

        indexes = {
            name: definition
            for name, definition in db.execute(
                text(
                    """
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND tablename = 'memory_record'
                    """
                )
            )
        }
        assert "ix_memory_record_org_scope_status_updated" in indexes
        assert "ix_memory_record_project_status_updated" in indexes
        assert "ix_memory_record_project_embedding_profile" in indexes
        assert "ix_memory_record_retrieval_text_fts" in indexes
        assert "ix_memory_record_embedding_hnsw" in indexes
        assert "vector_cosine_ops" in indexes["ix_memory_record_embedding_hnsw"]

        review_columns = {
            row[0]
            for row in db.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'memory_graph_review_decision'
                    """
                )
            )
        }
        assert {
            "org_id",
            "project_id",
            "proposal_memory_record_id",
            "item_id",
            "item_type",
            "proposal_fingerprint",
            "decision",
            "reviewer_user_id",
            "reviewed_at",
        } <= review_columns
    finally:
        db.close()
