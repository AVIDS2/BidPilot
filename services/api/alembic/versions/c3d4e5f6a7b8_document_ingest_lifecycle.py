"""make source-document ingest state and locators durable

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _foreign_keys(table_name: str) -> set[str]:
    return {
        foreign_key["name"]
        for foreign_key in sa.inspect(op.get_bind()).get_foreign_keys(table_name)
        if foreign_key.get("name")
    }


def _indexes(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _unique_constraints(table_name: str) -> set[str]:
    return {
        constraint["name"]
        for constraint in sa.inspect(op.get_bind()).get_unique_constraints(table_name)
        if constraint.get("name")
    }


def upgrade() -> None:
    source_columns = _columns("source_document")
    if "version_number" not in source_columns:
        op.add_column(
            "source_document",
            sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        )
    if "supersedes_document_id" not in source_columns:
        op.add_column(
            "source_document",
            sa.Column("supersedes_document_id", sa.String(length=36), nullable=True),
        )
    if "parse_error_code" not in source_columns:
        op.add_column(
            "source_document",
            sa.Column("parse_error_code", sa.String(length=100), nullable=True),
        )
    if "parsed_at" not in source_columns:
        op.add_column(
            "source_document",
            sa.Column("parsed_at", sa.DateTime(), nullable=True),
        )
    if "index_status" not in source_columns:
        op.add_column(
            "source_document",
            sa.Column("index_status", sa.String(length=30), nullable=False, server_default="pending"),
        )
    if "index_error_code" not in source_columns:
        op.add_column(
            "source_document",
            sa.Column("index_error_code", sa.String(length=100), nullable=True),
        )
    if "indexed_at" not in source_columns:
        op.add_column(
            "source_document",
            sa.Column("indexed_at", sa.DateTime(), nullable=True),
        )

    # A pre-contract demo used "completed" for parsed source documents.
    # Normalize that legacy UI-only value before deriving the durable index state.
    op.execute("UPDATE source_document SET parse_status = 'parsed' WHERE parse_status = 'completed'")
    op.execute(
        """
        UPDATE source_document AS document
        SET index_status = CASE
            WHEN document.parse_status = 'parsed'
                 AND EXISTS (
                     SELECT 1
                     FROM knowledge_chunk AS chunk
                     WHERE chunk.source_document_id = document.id
                       AND chunk.embedding_status = 'success'
                 ) THEN 'indexed'
            WHEN document.parse_status = 'parsed'
                 AND EXISTS (
                     SELECT 1
                     FROM knowledge_chunk AS chunk
                     WHERE chunk.source_document_id = document.id
                 ) THEN 'degraded'
            ELSE 'pending'
        END
        WHERE document.index_status IS NULL OR document.index_status = 'pending'
        """
    )

    if "fk_source_document_supersedes_document" not in _foreign_keys("source_document"):
        op.create_foreign_key(
            "fk_source_document_supersedes_document",
            "source_document",
            "source_document",
            ["supersedes_document_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if "uq_source_document_supersedes_document" not in _unique_constraints("source_document"):
        op.create_unique_constraint(
            "uq_source_document_supersedes_document",
            "source_document",
            ["supersedes_document_id"],
        )
    if "ix_source_document_bundle_ingestion_state" not in _indexes("source_document"):
        op.create_index(
            "ix_source_document_bundle_ingestion_state",
            "source_document",
            ["bundle_id", "parse_status", "index_status"],
        )

    chunk_columns = _columns("knowledge_chunk")
    if "chunk_key" not in chunk_columns:
        op.add_column(
            "knowledge_chunk",
            sa.Column("chunk_key", sa.String(length=64), nullable=True),
        )
    if "uq_knowledge_chunk_document_key" not in _unique_constraints("knowledge_chunk"):
        op.create_unique_constraint(
            "uq_knowledge_chunk_document_key",
            "knowledge_chunk",
            ["source_document_id", "chunk_key"],
        )


def downgrade() -> None:
    if "uq_knowledge_chunk_document_key" in _unique_constraints("knowledge_chunk"):
        op.drop_constraint(
            "uq_knowledge_chunk_document_key",
            "knowledge_chunk",
            type_="unique",
        )
    if "chunk_key" in _columns("knowledge_chunk"):
        op.drop_column("knowledge_chunk", "chunk_key")

    if "ix_source_document_bundle_ingestion_state" in _indexes("source_document"):
        op.drop_index("ix_source_document_bundle_ingestion_state", table_name="source_document")
    if "uq_source_document_supersedes_document" in _unique_constraints("source_document"):
        op.drop_constraint(
            "uq_source_document_supersedes_document",
            "source_document",
            type_="unique",
        )
    if "fk_source_document_supersedes_document" in _foreign_keys("source_document"):
        op.drop_constraint(
            "fk_source_document_supersedes_document",
            "source_document",
            type_="foreignkey",
        )
    for column_name in (
        "indexed_at",
        "index_error_code",
        "index_status",
        "parsed_at",
        "parse_error_code",
        "supersedes_document_id",
        "version_number",
    ):
        if column_name in _columns("source_document"):
            op.drop_column("source_document", column_name)
