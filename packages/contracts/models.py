"""Shared SQLAlchemy models for all BidPilot services.

Both the API and Worker import models from this module.
Alembic migrations are generated against these models.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
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
    workspace_kind: Mapped[str] = mapped_column(String(30), nullable=False, default="team")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    users: Mapped[list["User"]] = relationship(back_populates="organization")
    memberships: Mapped[list["OrganizationMembership"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    subscription: Mapped["OrganizationSubscription | None"] = relationship(
        back_populates="organization",
        uselist=False,
        cascade="all, delete-orphan",
    )
    projects: Mapped[list["Project"]] = relationship(back_populates="organization")
    teams: Mapped[list["Team"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    membership_events: Mapped[list["OrganizationMembershipEvent"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "workspace_kind IN ('personal', 'team')",
            name="ck_organization_workspace_kind",
        ),
    )


class OrganizationMembership(Base):
    """Durable organization membership; ``User.org_id`` remains active context."""

    __tablename__ = "organization_membership"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="member")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime)

    organization: Mapped["Organization"] = relationship(back_populates="memberships")
    user: Mapped["User"] = relationship(back_populates="organization_memberships")

    __table_args__ = (
        UniqueConstraint("org_id", "user_id", name="uq_organization_membership_org_user"),
        Index("ix_organization_membership_org_status", "org_id", "status"),
        Index("ix_organization_membership_user_status", "user_id", "status"),
    )


class OrganizationMembershipEvent(Base):
    """Immutable organization-level collaboration audit evidence."""

    __tablename__ = "organization_membership_event"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
    )
    membership_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("organization_membership.id", ondelete="SET NULL"),
    )
    actor_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="SET NULL"),
    )
    target_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="SET NULL"),
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    organization: Mapped["Organization"] = relationship(back_populates="membership_events")

    __table_args__ = (
        Index("ix_organization_membership_event_org_created", "org_id", "created_at"),
        Index("ix_organization_membership_event_target_created", "target_user_id", "created_at"),
    )


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
    organization_memberships: Mapped[list["OrganizationMembership"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    project_memberships: Mapped[list["ProjectMember"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    subscription: Mapped["Subscription"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    provider_configs: Mapped[list["ProviderConfig"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Subscription(Base):
    __tablename__ = "subscription"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(30), nullable=False, default="starter")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255))
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    # Stripe does not guarantee webhook delivery order. This lets the billing
    # control plane ignore an older event that arrives after a newer state.
    stripe_state_event_created_at: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="subscription")


class OrganizationSubscription(Base):
    """Commercial entitlement state for one organization workspace.

    User subscriptions remain only as a migration fallback. New commercial
    decisions must resolve through this record and active membership.
    """

    __tablename__ = "organization_subscription"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organization.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    plan: Mapped[str] = mapped_column(String(30), nullable=False, default="starter")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    seat_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    billable_seat_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    billing_owner_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="RESTRICT"),
        nullable=False,
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255))
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    stripe_subscription_item_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    stripe_state_event_created_at: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )

    organization: Mapped["Organization"] = relationship(back_populates="subscription")

    __table_args__ = (
        CheckConstraint("seat_limit >= 1", name="ck_organization_subscription_seat_limit"),
        CheckConstraint(
            "billable_seat_count >= 0",
            name="ck_organization_subscription_billable_seat_count",
        ),
        Index("ix_organization_subscription_billing_owner", "billing_owner_user_id"),
    )


class StripeWebhookEvent(Base):
    """A minimal immutable receipt ledger for signed Stripe webhook events.

    Raw webhook payloads are intentionally not retained here: they may include
    customer data and are not needed for replay protection or operational audit.
    """

    __tablename__ = "stripe_webhook_event"

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    event_created_at: Mapped[int] = mapped_column(Integer, nullable=False)
    livemode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="SET NULL"),
    )
    org_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("organization.id", ondelete="SET NULL"),
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255))
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255))
    received_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        Index("ix_stripe_webhook_event_created_at", "event_created_at"),
        Index("ix_stripe_webhook_event_user_received", "user_id", "received_at"),
        Index("ix_stripe_webhook_event_org_received", "org_id", "received_at"),
    )


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
    members: Mapped[list["ProjectMember"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    bundles: Mapped[list["Bundle"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class ProjectMember(Base):
    __tablename__ = "project_member"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="contributor")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    project: Mapped["Project"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="project_memberships")

    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member_project_user"),
    )


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


class AssistantAttachment(Base):
    """A user-owned file staged for a bounded Assistant turn.

    Staged objects are deliberately separate from project evidence until an
    authorized user approves the project-ingestion capability.
    """

    __tablename__ = "assistant_attachment"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: f"att_{uuid.uuid4().hex}",
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organization.id"), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("project.id", ondelete="SET NULL"),
        index=True,
    )
    bundle_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("bundle.id", ondelete="SET NULL"),
        index=True,
    )
    document_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("source_document.id", ondelete="SET NULL"),
        index=True,
    )
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="file")
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    extraction_status: Mapped[str] = mapped_column(String(30), nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    extraction_error: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="staged", index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    attached_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        Index("ix_assistant_attachment_owner_status_expiry", "user_id", "org_id", "status", "expires_at"),
    )


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
    retrieval_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )
    embedding_profile: Mapped[str | None] = mapped_column(String(500))
    embedding_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    embedding_updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    embedding_error_code: Mapped[str | None] = mapped_column(String(100))


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

    source_document: Mapped["SourceDocument | None"] = relationship()
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

    source_document: Mapped["SourceDocument | None"] = relationship()
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
    parent_execution_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("execution_run.id", ondelete="SET NULL"),
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    run_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    input_json: Mapped[dict | None] = mapped_column(JSON)
    output_json: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        UniqueConstraint("parent_execution_run_id", "attempt_number", name="uq_execution_run_parent_attempt"),
    )


class TaskOutboxEvent(Base):
    """Durable at-least-once task delivery record for workflow commands."""

    __tablename__ = "task_outbox_event"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("project.id", ondelete="SET NULL"),
    )
    execution_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("execution_run.id", ondelete="SET NULL"),
    )
    runtime_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("runtime_run.id", ondelete="SET NULL"),
    )
    task_name: Mapped[str] = mapped_column(String(200), nullable=False)
    args_json: Mapped[list] = mapped_column(JSON, nullable=False)
    kwargs_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    deduplication_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    dispatch_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivery_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("org_id", "deduplication_key", name="uq_task_outbox_org_deduplication"),
        CheckConstraint("dispatch_attempts >= 0", name="ck_task_outbox_dispatch_attempts"),
        CheckConstraint("delivery_attempts >= 0", name="ck_task_outbox_delivery_attempts"),
        Index("ix_task_outbox_status_available", "status", "available_at"),
        Index("ix_task_outbox_execution_run", "execution_run_id"),
    )


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


class OrganizationUsageBudget(Base):
    """Optional organization token caps layered on top of plan quotas."""

    __tablename__ = "organization_usage_budget"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organization.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    official_monthly_token_limit: Mapped[int | None] = mapped_column(BigInteger)
    byok_monthly_token_limit: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "official_monthly_token_limit IS NULL OR official_monthly_token_limit >= 0",
            name="ck_organization_usage_budget_official_tokens",
        ),
        CheckConstraint(
            "byok_monthly_token_limit IS NULL OR byok_monthly_token_limit >= 0",
            name="ck_organization_usage_budget_byok_tokens",
        ),
    )


class OrganizationUsageBudgetEvent(Base):
    """Immutable organization-level evidence for AI token-cap changes."""

    __tablename__ = "organization_usage_budget_event"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="SET NULL"),
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    previous_limits_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_limits_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_organization_usage_budget_event_org_created", "org_id", "created_at"),
    )


class ModelUsageReservation(Base):
    """Pre-dispatch capacity hold for a potentially billable model operation."""

    __tablename__ = "model_usage_reservation"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("user.id", ondelete="SET NULL"))
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("project.id", ondelete="SET NULL"))
    execution_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("execution_run.id", ondelete="SET NULL"),
    )
    runtime_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("runtime_run.id", ondelete="SET NULL"),
    )
    provider_source: Mapped[str] = mapped_column(String(30), nullable=False)
    workload: Mapped[str] = mapped_column(String(80), nullable=False)
    reservation_key: Mapped[str] = mapped_column(String(255), nullable=False)
    reserved_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="reserved")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "reservation_key", name="uq_model_usage_reservation_org_key"),
        CheckConstraint("reserved_tokens > 0", name="ck_model_usage_reservation_tokens"),
        Index("ix_model_usage_reservation_org_status_expiry", "org_id", "status", "expires_at"),
        Index("ix_model_usage_reservation_execution_run", "execution_run_id"),
        Index("ix_model_usage_reservation_runtime_run", "runtime_run_id"),
    )


class ModelUsageRecord(Base):
    """Immutable provider-reported token counters for one model invocation."""

    __tablename__ = "model_usage_record"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("user.id", ondelete="SET NULL"))
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("project.id", ondelete="SET NULL"))
    execution_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("execution_run.id", ondelete="SET NULL"),
    )
    runtime_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("runtime_run.id", ondelete="SET NULL"),
    )
    provider_config_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("provider_config.id", ondelete="SET NULL"),
    )
    provider_source: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(30), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    workload: Mapped[str] = mapped_column(String(80), nullable=False)
    input_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    measurement_source: Mapped[str] = mapped_column(String(50), nullable=False, default="provider_reported")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("input_tokens >= 0", name="ck_model_usage_record_input_tokens"),
        CheckConstraint("output_tokens >= 0", name="ck_model_usage_record_output_tokens"),
        CheckConstraint("reasoning_tokens >= 0", name="ck_model_usage_record_reasoning_tokens"),
        CheckConstraint("cache_read_tokens >= 0", name="ck_model_usage_record_cache_read_tokens"),
        CheckConstraint("cache_write_tokens >= 0", name="ck_model_usage_record_cache_write_tokens"),
        CheckConstraint("total_tokens >= 0", name="ck_model_usage_record_total_tokens"),
        Index("ix_model_usage_record_org_source_created", "org_id", "provider_source", "created_at"),
        Index("ix_model_usage_record_execution_run", "execution_run_id"),
        Index("ix_model_usage_record_runtime_run", "runtime_run_id"),
    )


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


# ── Unified Runtime ─────────────────────────────────────────────────────────


class RuntimeRun(Base):
    __tablename__ = "runtime_run"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="queued")
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organization.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("project.id", ondelete="SET NULL"))
    conversation_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("chat_conversation.id", ondelete="SET NULL"),
    )
    parent_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("runtime_run.id", ondelete="SET NULL"),
    )
    execution_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("execution_run.id", ondelete="SET NULL"),
    )
    engine: Mapped[str] = mapped_column(String(80), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    provider_config_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("provider_config.id", ondelete="SET NULL"),
    )
    model: Mapped[str | None] = mapped_column(String(255))
    reasoning_effort: Mapped[str | None] = mapped_column(String(30))
    policy_snapshot_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    input_json: Mapped[dict | None] = mapped_column(JSON)
    result_json: Mapped[dict | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("org_id", "idempotency_key", name="uq_runtime_run_org_idempotency"),
        Index("ix_runtime_run_org_status_created", "org_id", "status", "created_at"),
        Index("ix_runtime_run_project_created", "project_id", "created_at"),
        Index("ix_runtime_run_conversation_created", "conversation_id", "created_at"),
    )


class RuntimeEvent(Base):
    __tablename__ = "runtime_event"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("runtime_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    public_summary: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_runtime_event_run_sequence"),
        Index("ix_runtime_event_run_sequence", "run_id", "sequence"),
    )


class RuntimeAction(Base):
    __tablename__ = "runtime_action"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("runtime_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    action_key: Mapped[str] = mapped_column(String(255), nullable=False)
    capability_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    risk_level: Mapped[str] = mapped_column(String(40), nullable=False)
    policy_outcome: Mapped[str] = mapped_column(String(40), nullable=False)
    approval_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    arguments_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result_json: Mapped[dict | None] = mapped_column(JSON)
    public_summary: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        UniqueConstraint("run_id", "action_key", name="uq_runtime_action_run_action_key"),
        Index("ix_runtime_action_run_status", "run_id", "status"),
    )


class RuntimeApproval(Base):
    __tablename__ = "runtime_approval"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    action_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("runtime_action.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), nullable=False)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organization.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    decision_json: Mapped[dict | None] = mapped_column(JSON)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("action_id", name="uq_runtime_approval_action"),
        Index("ix_runtime_approval_user_status", "user_id", "status"),
        Index("ix_runtime_approval_org_status", "org_id", "status"),
    )


# ── Provider Config ─────────────────────────────────────────────────────────


class ProviderConfig(Base):
    __tablename__ = "provider_config"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="custom-openai",
        server_default="custom-openai",
    )
    api_key: Mapped[str] = mapped_column(Text, nullable=False)
    api_url: Mapped[str | None] = mapped_column(String(500))
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="provider_configs")


# ── Governed Memory / Bid Wiki ──────────────────────────────────────────────


class MemoryRecord(Base):
    __tablename__ = "memory_record"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organization.id"), nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("project.id", ondelete="SET NULL"))
    owner_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("user.id", ondelete="SET NULL"))
    scope: Mapped[str] = mapped_column(String(30), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="proposed")
    privacy_classification: Mapped[str] = mapped_column(String(30), nullable=False, default="internal")
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    structured_data_json: Mapped[dict | None] = mapped_column(JSON)
    content_fingerprint: Mapped[str | None] = mapped_column(String(64))
    retrieval_text: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    embedding_profile: Mapped[str | None] = mapped_column(String(500))
    embedding_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", server_default="pending")
    embedding_updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    embedding_error_code: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[float | None] = mapped_column(Float)
    origin: Mapped[str] = mapped_column(String(30), nullable=False)
    created_by_actor_type: Mapped[str] = mapped_column(String(30), nullable=False)
    created_by_actor_id: Mapped[str | None] = mapped_column(String(36))
    supersedes_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("memory_record.id", ondelete="SET NULL"),
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    evidence_links: Mapped[list["MemoryEvidenceLink"]] = relationship(
        back_populates="memory_record",
        cascade="all, delete-orphan",
    )
    events: Mapped[list["MemoryEvent"]] = relationship(
        back_populates="memory_record",
        cascade="all, delete-orphan",
    )
    graph_review_decisions: Mapped[list["MemoryGraphReviewDecision"]] = relationship(
        back_populates="proposal_memory_record",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_memory_record_org_scope_status_updated", "org_id", "scope", "status", "updated_at"),
        Index("ix_memory_record_project_status_updated", "project_id", "status", "updated_at"),
        Index("ix_memory_record_owner_status_updated", "owner_user_id", "status", "updated_at"),
        Index("ix_memory_record_project_embedding_profile", "project_id", "embedding_profile"),
    )


class MemoryEvidenceLink(Base):
    __tablename__ = "memory_evidence_link"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    memory_record_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("memory_record.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_id: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence_role: Mapped[str] = mapped_column(String(30), nullable=False, default="supports")
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    locator_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    memory_record: Mapped["MemoryRecord"] = relationship(back_populates="evidence_links")

    __table_args__ = (
        UniqueConstraint(
            "memory_record_id",
            "source_type",
            "source_id",
            "evidence_role",
            name="uq_memory_evidence_link_source",
        ),
        Index("ix_memory_evidence_link_source", "source_type", "source_id"),
    )


class MemoryEvent(Base):
    __tablename__ = "memory_event"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    memory_record_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("memory_record.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organization.id"), nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("project.id", ondelete="SET NULL"))
    actor_type: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    memory_record: Mapped["MemoryRecord"] = relationship(back_populates="events")

    __table_args__ = (
        Index("ix_memory_event_record_created", "memory_record_id", "created_at"),
        Index("ix_memory_event_org_created", "org_id", "created_at"),
    )


class MemoryGraphReviewDecision(Base):
    """One auditable decision for one item in a graph proposal."""

    __tablename__ = "memory_graph_review_decision"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organization.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
    )
    proposal_memory_record_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("memory_record.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_id: Mapped[str] = mapped_column(String(80), nullable=False)
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)
    proposal_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    decision_note: Mapped[str | None] = mapped_column(Text)
    reviewer_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="SET NULL"),
    )
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    proposal_memory_record: Mapped["MemoryRecord"] = relationship(back_populates="graph_review_decisions")

    __table_args__ = (
        UniqueConstraint(
            "proposal_memory_record_id",
            "item_id",
            name="uq_memory_graph_review_decision_item",
        ),
        Index("ix_memory_graph_review_project_decision", "project_id", "decision"),
        Index("ix_memory_graph_review_record_item", "proposal_memory_record_id", "item_type", "item_id"),
    )


class MemoryEntity(Base):
    __tablename__ = "memory_entity"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organization.id"), nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("project.id", ondelete="SET NULL"))
    memory_record_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("memory_record.id", ondelete="CASCADE"),
        nullable=False,
    )
    canonical_name: Mapped[str] = mapped_column(String(240), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    aliases_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_memory_entity_project_type_name", "project_id", "entity_type", "canonical_name"),
        Index("ix_memory_entity_org_status", "org_id", "status"),
    )


class MemoryRelation(Base):
    __tablename__ = "memory_relation"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organization.id"), nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("project.id", ondelete="SET NULL"))
    memory_record_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("memory_record.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_entity_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("memory_entity.id", ondelete="CASCADE"),
        nullable=False,
    )
    object_entity_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("memory_entity.id", ondelete="CASCADE"),
        nullable=False,
    )
    predicate: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "memory_record_id",
            "subject_entity_id",
            "object_entity_id",
            "predicate",
            name="uq_memory_relation_record_edge",
        ),
        Index("ix_memory_relation_project_status", "project_id", "status"),
        Index("ix_memory_relation_subject", "subject_entity_id", "status"),
        Index("ix_memory_relation_object", "object_entity_id", "status"),
    )


class MemoryCompilationRun(Base):
    __tablename__ = "memory_compilation_run"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organization.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("project.id"), nullable=False)
    bundle_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("bundle.id", ondelete="SET NULL"))
    initiated_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("user.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    input_source_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    input_memory_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    embedding_profile: Mapped[str | None] = mapped_column(String(500))
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    result_json: Mapped[dict | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(100))
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_memory_compilation_run_project_status_created", "project_id", "status", "created_at"),
        Index("ix_memory_compilation_run_org_created", "org_id", "created_at"),
    )


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
