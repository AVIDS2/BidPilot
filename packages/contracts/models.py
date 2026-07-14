"""Shared SQLAlchemy models for all BidPilot services.

Both the API and Worker import models from this module.
Alembic migrations are generated against these models.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Organization & Team ──────────────────────────────────────────────────────


class Organization(Base):
    __tablename__ = "organization"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    users: Mapped[list["User"]] = relationship(back_populates="organization")
    projects: Mapped[list["Project"]] = relationship(back_populates="organization")
    teams: Mapped[list["Team"]] = relationship(back_populates="organization", cascade="all, delete-orphan")


class Team(Base):
    __tablename__ = "team"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organization.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    organization: Mapped["Organization"] = relationship(back_populates="teams")
    members: Mapped[list["TeamMember"]] = relationship(back_populates="team", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("org_id", "slug", name="uq_team_org_slug"),)


class TeamMember(Base):
    __tablename__ = "team_member"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    team_id: Mapped[str] = mapped_column(String(36), ForeignKey("team.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    team: Mapped["Team"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship()

    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_team_member_team_user"),)


# ── User & Auth ──────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "user"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organization.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="member")
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    organization: Mapped["Organization"] = relationship(back_populates="users")
    subscription: Mapped["Subscription"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    provider_configs: Mapped[list["ProviderConfig"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Subscription(Base):
    __tablename__ = "subscription"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(30), nullable=False, default="starter")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="subscription")


class RefreshToken(Base):
    __tablename__ = "refresh_token"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Invitation(Base):
    __tablename__ = "invitation"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organization.id"), nullable=False)
    invited_by: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Notification(Base):
    __tablename__ = "notification"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(30), nullable=False, default="system")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    link: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ── Project & Documents ──────────────────────────────────────────────────────


class Project(Base):
    __tablename__ = "project"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organization.id"), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    scenario_package: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    organization: Mapped["Organization"] = relationship(back_populates="projects")
    bundles: Mapped[list["Bundle"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Bundle(Base):
    __tablename__ = "bundle"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("project.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    ingest_status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    project: Mapped["Project"] = relationship(back_populates="bundles")
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
    parsed_assets: Mapped[list["ParsedAsset"]] = relationship(back_populates="source_document", cascade="all, delete-orphan")


class ParsedAsset(Base):
    __tablename__ = "parsed_asset"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_document_id: Mapped[str] = mapped_column(String(36), ForeignKey("source_document.id"), nullable=False)
    parser_name: Mapped[str] = mapped_column(String(100), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(30), nullable=False)
    content_json: Mapped[dict | None] = mapped_column(JSON)
    layout_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    source_document: Mapped["SourceDocument"] = relationship(back_populates="parsed_assets")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunk"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("project.id"), nullable=False)
    source_document_id: Mapped[str] = mapped_column(String(36), ForeignKey("source_document.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))


# ── Requirements & Evidence ──────────────────────────────────────────────────


class RequirementItem(Base):
    __tablename__ = "requirement_item"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("project.id"), nullable=False)
    section_key: Mapped[str] = mapped_column(String(100), nullable=False)
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    original_text: Mapped[str | None] = mapped_column(Text)
    source_document_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("source_document.id", ondelete="SET NULL"),
    )
    source_locator_json: Mapped[dict | None] = mapped_column(JSON)
    priority: Mapped[str] = mapped_column(String(30), nullable=False, default="normal")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    owner_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="SET NULL"),
        index=True,
    )
    reviewer_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="SET NULL"),
        index=True,
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime)
    verification_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="unverified",
        server_default="unverified",
        index=True,
    )
    extraction_confidence: Mapped[float | None] = mapped_column(Float)
    lock_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )

    bid_profile: Mapped["BidRequirementProfile | None"] = relationship(
        back_populates="requirement",
        cascade="all, delete-orphan",
        uselist=False,
    )
    evidence_links: Mapped[list["RequirementEvidenceLink"]] = relationship(
        back_populates="requirement",
        cascade="all, delete-orphan",
    )
    claim_links: Mapped[list["RequirementClaimLink"]] = relationship(
        back_populates="requirement",
        cascade="all, delete-orphan",
    )
    decisions: Mapped[list["RequirementDecision"]] = relationship(
        back_populates="requirement",
        cascade="all, delete-orphan",
    )

    __mapper_args__ = {"version_id_col": lock_version}
    __table_args__ = (
        Index("ix_requirement_item_project_verification", "project_id", "verification_status"),
    )


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

    requirement_links: Mapped[list["RequirementEvidenceLink"]] = relationship(
        back_populates="evidence",
        cascade="all, delete-orphan",
    )
    claim_links: Mapped[list["ClaimEvidenceLink"]] = relationship(
        back_populates="evidence",
        cascade="all, delete-orphan",
    )


class BidRequirementProfile(Base):
    __tablename__ = "bid_requirement_profile"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    requirement_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("requirement_item.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    bid_category: Mapped[str] = mapped_column(String(30), nullable=False, default="technical", index=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    score_weight: Mapped[float | None] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(30), nullable=False, default="normal", index=True)
    coverage_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="uncovered",
        server_default="uncovered",
        index=True,
    )
    evidence_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="missing",
        server_default="missing",
        index=True,
    )
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime)
    submission_metadata_json: Mapped[dict | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )

    requirement: Mapped["RequirementItem"] = relationship(back_populates="bid_profile")


class RequirementEvidenceLink(Base):
    __tablename__ = "requirement_evidence_link"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    requirement_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("requirement_item.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("evidence.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation_type: Mapped[str] = mapped_column(String(30), nullable=False, default="supports")
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False, default="unverified")
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    requirement: Mapped["RequirementItem"] = relationship(back_populates="evidence_links")
    evidence: Mapped["Evidence"] = relationship(back_populates="requirement_links")

    __table_args__ = (
        UniqueConstraint(
            "requirement_id",
            "evidence_id",
            "relation_type",
            name="uq_requirement_evidence_relation",
        ),
    )


class Claim(Base):
    __tablename__ = "claim"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(30), nullable=False, default="factual")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    section_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("section_version.id", ondelete="SET NULL"),
    )
    generation_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("execution_run.id", ondelete="SET NULL"),
    )
    created_by_actor: Mapped[str] = mapped_column(String(30), nullable=False, default="ai")
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )

    requirement_links: Mapped[list["RequirementClaimLink"]] = relationship(
        back_populates="claim",
        cascade="all, delete-orphan",
    )
    evidence_links: Mapped[list["ClaimEvidenceLink"]] = relationship(
        back_populates="claim",
        cascade="all, delete-orphan",
    )


class RequirementClaimLink(Base):
    __tablename__ = "requirement_claim_link"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    requirement_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("requirement_item.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    claim_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("claim.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    coverage_role: Mapped[str] = mapped_column(String(30), nullable=False, default="direct")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    requirement: Mapped["RequirementItem"] = relationship(back_populates="claim_links")
    claim: Mapped["Claim"] = relationship(back_populates="requirement_links")

    __table_args__ = (
        UniqueConstraint("requirement_id", "claim_id", name="uq_requirement_claim"),
    )


class ClaimEvidenceLink(Base):
    __tablename__ = "claim_evidence_link"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    claim_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("claim.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("evidence.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation_type: Mapped[str] = mapped_column(String(30), nullable=False, default="supports")
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False, default="unverified")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    claim: Mapped["Claim"] = relationship(back_populates="evidence_links")
    evidence: Mapped["Evidence"] = relationship(back_populates="claim_links")

    __table_args__ = (
        UniqueConstraint(
            "claim_id",
            "evidence_id",
            "relation_type",
            name="uq_claim_evidence_relation",
        ),
    )


class RequirementDecision(Base):
    __tablename__ = "requirement_decision"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    requirement_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("requirement_item.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision_type: Mapped[str] = mapped_column(String(30), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    requested_by_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user.id"),
        nullable=False,
    )
    approved_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)

    requirement: Mapped["RequirementItem"] = relationship(back_populates="decisions")


class ReadinessPack(Base):
    __tablename__ = "readiness_pack"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    formula_version: Mapped[str] = mapped_column(String(30), nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="generated")
    summary_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    xlsx_storage_key: Mapped[str | None] = mapped_column(String(500))
    docx_storage_key: Mapped[str | None] = mapped_column(String(500))
    generated_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "version_number",
            name="uq_readiness_pack_project_version",
        ),
    )


# ── Deliverables & Drafting ──────────────────────────────────────────────────


class Deliverable(Base):
    __tablename__ = "deliverable"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("project.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    current_version_id: Mapped[str | None] = mapped_column(String(36))
    export_status: Mapped[str] = mapped_column(String(30), nullable=False, default="not_exported")
    export_storage_key: Mapped[str | None] = mapped_column(String(500))

    sections: Mapped[list["DeliverableSection"]] = relationship(back_populates="deliverable", cascade="all, delete-orphan")


class DeliverableSection(Base):
    __tablename__ = "deliverable_section"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    deliverable_id: Mapped[str] = mapped_column(String(36), ForeignKey("deliverable.id"), nullable=False)
    section_key: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    assignee_type: Mapped[str] = mapped_column(String(30), nullable=False, default="ai")

    deliverable: Mapped["Deliverable"] = relationship(back_populates="sections")
    versions: Mapped[list["SectionVersion"]] = relationship(back_populates="section", cascade="all, delete-orphan")


class SectionVersion(Base):
    __tablename__ = "section_version"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    deliverable_section_id: Mapped[str] = mapped_column(String(36), ForeignKey("deliverable_section.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_json: Mapped[dict | None] = mapped_column(JSON)
    content_markdown: Mapped[str | None] = mapped_column(Text)
    created_by_actor: Mapped[str] = mapped_column(String(30), nullable=False, default="ai")
    generation_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("execution_run.id"))

    section: Mapped["DeliverableSection"] = relationship(back_populates="versions")


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


# ── Review ───────────────────────────────────────────────────────────────────


class ReviewThread(Base):
    __tablename__ = "review_thread"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    deliverable_section_id: Mapped[str] = mapped_column(String(36), ForeignKey("deliverable_section.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    opened_by: Mapped[str] = mapped_column(String(36), nullable=False)
    resolved_by: Mapped[str | None] = mapped_column(String(36))


class ReviewComment(Base):
    __tablename__ = "review_comment"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    review_thread_id: Mapped[str] = mapped_column(String(36), ForeignKey("review_thread.id"), nullable=False)
    author_type: Mapped[str] = mapped_column(String(30), nullable=False)
    author_id: Mapped[str] = mapped_column(String(36), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ── Audit & Usage ────────────────────────────────────────────────────────────


class AuditEvent(Base):
    __tablename__ = "audit_event"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("project.id"), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class UsageEvent(Base):
    __tablename__ = "usage_event"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), nullable=False)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organization.id"), nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("project.id"))
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    provider_source: Mapped[str] = mapped_column(String(30), nullable=False)
    units: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    execution_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("execution_run.id"))
    period_key: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AssistantActionAudit(Base):
    __tablename__ = "assistant_action_audit"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_conversation.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), nullable=False)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organization.id"), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(80), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(30), nullable=False)
    approval_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="risky_only")
    arguments_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running")
    result_summary: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)


class AssistantApproval(Base):
    __tablename__ = "assistant_approval"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_conversation.id", ondelete="CASCADE"), nullable=False)
    action_audit_id: Mapped[str] = mapped_column(String(36), ForeignKey("assistant_action_audit.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), nullable=False)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organization.id"), nullable=False)
    thread_id: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(80), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(30), nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ── Provider Config ──────────────────────────────────────────────────────────


class ProviderConfig(Base):
    __tablename__ = "provider_config"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(20), nullable=False)
    api_key: Mapped[str] = mapped_column(Text, nullable=False)
    api_url: Mapped[str | None] = mapped_column(String(500))
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="provider_configs")


# ── Chat ─────────────────────────────────────────────────────────────────────


class ChatConversation(Base):
    __tablename__ = "chat_conversation"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("project.id"))
    title: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")
    task_state: Mapped["ChatTaskState | None"] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_message"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_conversation.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversation: Mapped["ChatConversation"] = relationship(back_populates="messages")


class ChatTaskState(Base):
    __tablename__ = "chat_task_state"

    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chat_conversation.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="idle")
    tool_name: Mapped[str | None] = mapped_column(String(80))
    arguments_json: Mapped[dict | None] = mapped_column(JSON)
    missing_fields_json: Mapped[dict | None] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    conversation: Mapped["ChatConversation"] = relationship(back_populates="task_state")
