import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, String, Text, Float, Integer, JSON, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Project(Base):
    __tablename__ = "project"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    scenario_package: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Bundle(Base):
    __tablename__ = "bundle"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("project.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    ingest_status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    source_documents: Mapped[list["SourceDocument"]] = relationship(back_populates="bundle", cascade="all, delete-orphan")


class SourceDocument(Base):
    __tablename__ = "source_document"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    bundle_id: Mapped[str] = mapped_column(String(36), ForeignKey("bundle.id"), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    parse_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")

    bundle: Mapped["Bundle"] = relationship(back_populates="source_documents")


class ParsedAsset(Base):
    __tablename__ = "parsed_asset"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_document_id: Mapped[str] = mapped_column(String(36), ForeignKey("source_document.id"), nullable=False)
    parser_name: Mapped[str] = mapped_column(String(100), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(30), nullable=False)
    content_json: Mapped[dict | None] = mapped_column(JSON)
    layout_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunk"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("project.id"), nullable=False)
    source_document_id: Mapped[str] = mapped_column(String(36), ForeignKey("source_document.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))


class RequirementItem(Base):
    __tablename__ = "requirement_item"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("project.id"), nullable=False)
    section_key: Mapped[str] = mapped_column(String(100), nullable=False)
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(30), nullable=False, default="normal")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")


class DeliverableSection(Base):
    __tablename__ = "deliverable_section"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    deliverable_id: Mapped[str] = mapped_column(String(36), ForeignKey("deliverable.id"), nullable=False)
    section_key: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    assignee_type: Mapped[str] = mapped_column(String(30), nullable=False, default="ai")


class SectionVersion(Base):
    __tablename__ = "section_version"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    deliverable_section_id: Mapped[str] = mapped_column(String(36), ForeignKey("deliverable_section.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_json: Mapped[dict | None] = mapped_column(JSON)
    content_markdown: Mapped[str | None] = mapped_column(Text)
    created_by_actor: Mapped[str] = mapped_column(String(30), nullable=False, default="ai")
    generation_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("execution_run.id"))


class ExecutionRun(Base):
    __tablename__ = "execution_run"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("project.id"), nullable=False)
    run_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    input_json: Mapped[dict | None] = mapped_column(JSON)
    output_json: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("project.id"), nullable=False)
    section_version_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("section_version.id"))
    source_document_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("source_document.id"))
    chunk_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("knowledge_chunk.id"))
    quote_text: Mapped[str] = mapped_column(Text, nullable=False)
    locator_json: Mapped[dict | None] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column(Float)
