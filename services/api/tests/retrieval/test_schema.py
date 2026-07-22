import pytest
from sqlalchemy import text

from app.db import SessionLocal


def test_retrieval_2_postgres_schema_has_profile_fields_and_indexes() -> None:
    db = SessionLocal()
    try:
        if db.get_bind().dialect.name != "postgresql":
            pytest.skip("retrieval schema indexes are PostgreSQL-specific")

        columns = {
            row[0]
            for row in db.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'knowledge_chunk'
                    """
                )
            )
        }
        assert {
            "retrieval_text",
            "embedding_profile",
            "embedding_status",
            "embedding_updated_at",
            "embedding_error_code",
        } <= columns

        extensions = set(
            db.execute(
                text(
                    """
                    SELECT extname
                    FROM pg_extension
                    WHERE extname IN ('vector', 'pg_trgm')
                    """
                )
            ).scalars()
        )
        assert extensions == {"vector", "pg_trgm"}

        indexes = {
            name: definition
            for name, definition in db.execute(
                text(
                    """
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND tablename = 'knowledge_chunk'
                    """
                )
            )
        }
        assert "ix_knowledge_chunk_project_id" in indexes
        assert "ix_knowledge_chunk_project_embedding_profile" in indexes
        assert "ix_knowledge_chunk_retrieval_text_fts" in indexes
        assert "ix_knowledge_chunk_content_trgm" in indexes
        assert "ix_knowledge_chunk_embedding_hnsw" in indexes
        assert "vector_cosine_ops" in indexes["ix_knowledge_chunk_embedding_hnsw"]
        assert "gin_trgm_ops" in indexes["ix_knowledge_chunk_content_trgm"]
        assert "to_tsvector" in indexes["ix_knowledge_chunk_retrieval_text_fts"]
    finally:
        db.close()
