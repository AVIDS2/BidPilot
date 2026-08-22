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
    true,
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


class NotificationPreference(Base):
    """Per-user channel and category choices for non-critical notifications.

    Business records, approvals and audit events are never conditional on this
    table. It only decides whether a user receives an in-app or email notice.
    Missing rows intentionally mean the conservative product default: all
    categories and both channels are enabled.
    """

    __tablename__ = "notification_preference"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    review_updates: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    agent_updates: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    radar_updates: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    material_updates: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


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


# ── Tender Radar ────────────────────────────────────────────────────────────


class NoticeSource(Base):
    """One organization-owned source of tender notices.

    ``rss`` and ``json_feed`` are polled by the worker. ``webhook`` sources
    are populated by a signed inbound integration endpoint. The source never
    stores a private-network URL: fetching is delegated to the guarded public
    HTTP importer.
    """

    __tablename__ = "notice_source"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    endpoint_url: Mapped[str | None] = mapped_column(String(2048))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    polling_interval_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60, server_default="60"
    )
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    items: Mapped[list["NoticeItem"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("kind IN ('rss', 'json_feed', 'webhook')", name="ck_notice_source_kind"),
        CheckConstraint("polling_interval_minutes BETWEEN 5 AND 1440", name="ck_notice_source_interval"),
        Index("ix_notice_source_org_active", "org_id", "is_active"),
    )


class NoticeSubscription(Base):
    """Saved organization search intent used to explain recommendation matches."""

    __tablename__ = "notice_subscription"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    keywords_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    regions_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    categories_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    budget_min: Mapped[float | None] = mapped_column(Float)
    budget_max: Mapped[float | None] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    matches: Mapped[list["NoticeMatch"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "budget_min IS NULL OR budget_max IS NULL OR budget_min <= budget_max",
            name="ck_notice_subscription_budget_range",
        ),
        Index("ix_notice_subscription_org_active", "org_id", "is_active"),
    )


class NoticeItem(Base):
    """One normalized opportunity, deduplicated inside its original source."""

    __tablename__ = "notice_item"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("notice_source.id", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    buyer_name: Mapped[str | None] = mapped_column(String(255))
    notice_type: Mapped[str] = mapped_column(String(40), nullable=False, default="other")
    region: Mapped[str | None] = mapped_column(String(120))
    category: Mapped[str | None] = mapped_column(String(120))
    budget_amount: Mapped[float | None] = mapped_column(Float)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    source_snapshot_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="new", server_default="new")
    saved_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="SET NULL")
    )
    converted_project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("project.id", ondelete="SET NULL"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    source: Mapped["NoticeSource"] = relationship(back_populates="items")
    matches: Mapped[list["NoticeMatch"]] = relationship(
        back_populates="notice", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "notice_type IN ('intent', 'tender', 'prequalification', 'rfi', 'other')",
            name="ck_notice_item_type",
        ),
        CheckConstraint(
            "status IN ('new', 'saved', 'ignored', 'converted')",
            name="ck_notice_item_status",
        ),
        UniqueConstraint("source_id", "external_id", name="uq_notice_item_source_external"),
        Index("ix_notice_item_org_status_created", "org_id", "status", "created_at"),
        Index("ix_notice_item_org_deadline", "org_id", "deadline_at"),
    )


class NoticeMatch(Base):
    """A durable recommendation and its human-readable matching reasons."""

    __tablename__ = "notice_match"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    notice_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("notice_item.id", ondelete="CASCADE"), nullable=False
    )
    subscription_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("notice_subscription.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    reasons_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    notice: Mapped["NoticeItem"] = relationship(back_populates="matches")
    subscription: Mapped["NoticeSubscription"] = relationship(back_populates="matches")

    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 100", name="ck_notice_match_score"),
        UniqueConstraint("notice_id", "subscription_id", name="uq_notice_match_notice_subscription"),
        Index("ix_notice_match_subscription_score", "subscription_id", "score"),
    )


# ── Business Webhooks ───────────────────────────────────────────────────────


class WebhookEndpoint(Base):
    """One organization-owned outbound webhook destination.

    The signing secret is encrypted at rest. It is only returned once when an
    endpoint is created or rotated, while all deliveries retain their own
    durable retry state.
    """

    __tablename__ = "webhook_endpoint"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    target_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    signing_secret_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    events_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    deliveries: Mapped[list["WebhookDelivery"]] = relationship(
        back_populates="endpoint", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_webhook_endpoint_org_active", "org_id", "is_active"),
    )


class WebhookDelivery(Base):
    """An immutable outbound event intent with at-least-once delivery state."""

    __tablename__ = "webhook_delivery"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    endpoint_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("webhook_endpoint.id", ondelete="CASCADE"), nullable=False
    )
    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", server_default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5, server_default="5")
    available_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_http_status: Mapped[int | None] = mapped_column(Integer)
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    endpoint: Mapped["WebhookEndpoint"] = relationship(back_populates="deliveries")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'delivering', 'delivered', 'failed')",
            name="ck_webhook_delivery_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_webhook_delivery_attempt_count"),
        CheckConstraint("max_attempts BETWEEN 1 AND 10", name="ck_webhook_delivery_max_attempts"),
        Index("ix_webhook_delivery_due", "status", "available_at"),
        Index("ix_webhook_delivery_endpoint_created", "endpoint_id", "created_at"),
        Index("ix_webhook_delivery_org_created", "org_id", "created_at"),
    )


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
    # Remote provenance is durable business data. It is empty for local uploads
    # and records the final imported URL for bounded Agent/web imports.
    source_url: Mapped[str | None] = mapped_column(String(2048))
    page_count: Mapped[int | None] = mapped_column(Integer)
    parse_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    parse_attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    # Each row is an immutable uploaded version. A replacement is explicit via
    # supersedes_document_id; filename matching is never used as implicit lineage.
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    supersedes_document_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("source_document.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Parser diagnostics are durable operational truth.  They allow users and
    # support tooling to distinguish a corrupt upload from a transient worker
    # failure without exposing an internal exception or storage path.
    parser_name: Mapped[str | None] = mapped_column(String(100))
    parser_version: Mapped[str | None] = mapped_column(String(50))
    parse_error_code: Mapped[str | None] = mapped_column(String(100))
    parse_error_detail: Mapped[str | None] = mapped_column(Text)
    parse_retryable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime)
    index_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    index_error_code: Mapped[str | None] = mapped_column(String(100))
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime)

    bundle: Mapped["Bundle"] = relationship(back_populates="source_documents")
    parsed_assets: Mapped[list["ParsedAsset"]] = relationship(back_populates="source_document", cascade="all, delete-orphan")

    # Replacements form a linear lineage (v1 -> v2 -> v3), never a fan-out of
    # conflicting successor versions for the same immutable source document.
    __table_args__ = (
        UniqueConstraint(
            "supersedes_document_id",
            name="uq_source_document_supersedes_document",
        ),
    )


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


class OpportunityAssessment(Base):
    """Project-scoped Go/No-Go scorecard and its current governed outcome."""

    __tablename__ = "opportunity_assessment"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", server_default="draft")
    decision: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending", server_default="pending", index=True
    )
    scorecard_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    risk_summary_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    rationale: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="SET NULL"), index=True
    )
    decided_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="SET NULL"), index=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    lock_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    decisions: Mapped[list["OpportunityAssessmentDecision"]] = relationship(
        back_populates="assessment",
        cascade="all, delete-orphan",
    )

    __mapper_args__ = {"version_id_col": lock_version}
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'ready', 'decided', 'archived')",
            name="ck_opportunity_assessment_status",
        ),
        CheckConstraint(
            "decision IN ('pending', 'go', 'no_go', 'conditional_go')",
            name="ck_opportunity_assessment_decision",
        ),
        Index("ix_opportunity_assessment_project_decision", "project_id", "decision"),
    )


class OpportunityAssessmentDecision(Base):
    """Immutable decision history; the assessment row only stores its latest state."""

    __tablename__ = "opportunity_assessment_decision"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    assessment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("opportunity_assessment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text)
    scorecard_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    risk_summary_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    decided_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    assessment: Mapped["OpportunityAssessment"] = relationship(back_populates="decisions")

    __table_args__ = (
        UniqueConstraint(
            "assessment_id", "sequence", name="uq_opportunity_assessment_decision_sequence"
        ),
        CheckConstraint(
            "decision IN ('go', 'no_go', 'conditional_go')",
            name="ck_opportunity_assessment_decision_value",
        ),
    )


class ContentLibraryEntry(Base):
    """Organization-owned reusable content. Draft model output is never auto-published."""

    __tablename__ = "content_library_entry"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False, default="answer")
    category: Mapped[str | None] = mapped_column(String(100), index=True)
    tags_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    lifecycle_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="draft", server_default="draft", index=True
    )
    review_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="draft", server_default="draft", index=True
    )
    owner_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="SET NULL"), index=True
    )
    effective_from: Mapped[datetime | None] = mapped_column(DateTime)
    effective_until: Mapped[datetime | None] = mapped_column(DateTime)
    supersedes_entry_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("content_library_entry.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    versions: Mapped[list["ContentLibraryVersion"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "lifecycle_status IN ('draft', 'published', 'archived')",
            name="ck_content_library_entry_lifecycle",
        ),
        CheckConstraint(
            "review_status IN ('draft', 'approved', 'rejected')",
            name="ck_content_library_entry_review",
        ),
        Index("ix_content_library_entry_org_lifecycle", "org_id", "lifecycle_status"),
    )


class ContentLibraryVersion(Base):
    """Immutable revision of a reusable answer, case study, template, or attachment note."""

    __tablename__ = "content_library_version"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    entry_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("content_library_entry.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_json: Mapped[dict | None] = mapped_column(JSON)
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    entry: Mapped["ContentLibraryEntry"] = relationship(back_populates="versions")

    __table_args__ = (
        UniqueConstraint("entry_id", "version_number", name="uq_content_library_version_number"),
        UniqueConstraint("entry_id", "content_hash", name="uq_content_library_version_hash"),
    )


class ContentLibraryUsage(Base):
    """A durable reference from a Bid Project to the exact library version it reused."""

    __tablename__ = "content_library_usage"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    entry_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("content_library_entry.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    content_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("content_library_version.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True
    )
    deliverable_section_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("deliverable_section.id", ondelete="SET NULL"), index=True
    )
    usage_purpose: Mapped[str] = mapped_column(String(50), nullable=False, default="reference")
    used_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "content_version_id",
            "project_id",
            "deliverable_section_id",
            "usage_purpose",
            name="uq_content_library_usage_target",
        ),
        Index("ix_content_library_usage_project_created", "project_id", "created_at"),
    )


class DocumentChangeSet(Base):
    """One deterministic comparison between an immutable document and its replacement."""

    __tablename__ = "document_change_set"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True
    )
    previous_document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_document.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    replacement_document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("source_document.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending_parse", server_default="pending_parse", index=True
    )
    summary_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="SET NULL"), index=True
    )
    reviewed_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="SET NULL"), index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    impacts: Mapped[list["DocumentChangeImpact"]] = relationship(
        back_populates="change_set", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_parse', 'analyzed', 'accepted', 'dismissed')",
            name="ck_document_change_set_status",
        ),
        UniqueConstraint(
            "project_id", "replacement_document_id", name="uq_document_change_set_project_replacement"
        ),
    )


class DocumentChangeImpact(Base):
    """One reviewable project fact caused by a source document replacement."""

    __tablename__ = "document_change_impact"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    change_set_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("document_change_set.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    impact_key: Mapped[str] = mapped_column(String(128), nullable=False)
    requirement_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("requirement_item.id", ondelete="SET NULL"), index=True
    )
    deliverable_section_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("deliverable_section.id", ondelete="SET NULL"), index=True
    )
    impact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(30), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="open", server_default="open", index=True
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    locator_json: Mapped[dict | None] = mapped_column(JSON)
    acknowledged_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="SET NULL")
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolved_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("user.id", ondelete="SET NULL")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    change_set: Mapped["DocumentChangeSet"] = relationship(back_populates="impacts")

    __table_args__ = (
        UniqueConstraint("change_set_id", "impact_key", name="uq_document_change_impact_key"),
        CheckConstraint(
            "status IN ('open', 'acknowledged', 'resolved', 'dismissed')",
            name="ck_document_change_impact_status",
        ),
        CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_document_change_impact_severity",
        ),
    )


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunk"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("project.id"), nullable=False)
    source_document_id: Mapped[str] = mapped_column(String(36), ForeignKey("source_document.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # Stable per immutable source-document version. Retries can safely replay a
    # parser result without creating a second chunk at the same locator.
    chunk_key: Mapped[str | None] = mapped_column(String(64))
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

    __table_args__ = (
        UniqueConstraint(
            "source_document_id",
            "chunk_key",
            name="uq_knowledge_chunk_document_key",
        ),
    )


# ── Requirements & Evidence ──────────────────────────────────────────────────


class EvidenceSet(Base):
    """Immutable, project-scoped evidence snapshot selected before a draft."""

    __tablename__ = "evidence_set"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    execution_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("execution_run.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_key: Mapped[str] = mapped_column(String(100), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_profile_id: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ready")
    degraded_reasons_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    rejected_reasons_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    unmet_requirement_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    items: Mapped[list["EvidenceSetItem"]] = relationship(
        back_populates="evidence_set",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "execution_run_id",
            "section_key",
            name="uq_evidence_set_run_section",
        ),
        Index("ix_evidence_set_project_section", "project_id", "section_key"),
    )


class EvidenceSetItem(Base):
    """One validated source/chunk snapshot belonging to an ``EvidenceSet``."""

    __tablename__ = "evidence_set_item"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    evidence_set_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("evidence_set.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("source_document.id", ondelete="RESTRICT"),
        nullable=False,
    )
    chunk_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("knowledge_chunk.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_document_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_document_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    locator_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    quote_text: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    retrieval_score: Mapped[float] = mapped_column(Float, nullable=False)
    retrieval_methods_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    selected_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    evidence_set: Mapped["EvidenceSet"] = relationship(back_populates="items")

    __table_args__ = (
        UniqueConstraint(
            "evidence_set_id",
            "chunk_id",
            name="uq_evidence_set_item_chunk",
        ),
    )


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
    # Stable identity for one extracted requirement from one immutable source
    # document version. Manual requirements intentionally keep this null.
    extraction_key: Mapped[str | None] = mapped_column(String(64))
    priority: Mapped[str] = mapped_column(String(30), nullable=False, default="normal")
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="untriaged",
        server_default="untriaged",
    )
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
        Index(
            "uq_requirement_item_project_extraction_key",
            "project_id",
            "extraction_key",
            unique=True,
        ),
    )


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("project.id"), nullable=False)
    section_version_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("section_version.id"))
    source_document_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("source_document.id"))
    chunk_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("knowledge_chunk.id"))
    evidence_set_item_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("evidence_set_item.id", ondelete="SET NULL"),
        index=True,
    )
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


class DeliverableExport(Base):
    """An immutable, storage-backed snapshot of approved deliverable content."""

    __tablename__ = "deliverable_export"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    deliverable_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("deliverable.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="generating")
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    approved_versions_json: Mapped[list] = mapped_column(JSON, nullable=False)
    docx_storage_key: Mapped[str | None] = mapped_column(String(500))
    pdf_storage_key: Mapped[str | None] = mapped_column(String(500))
    docx_sha256: Mapped[str | None] = mapped_column(String(64))
    pdf_sha256: Mapped[str | None] = mapped_column(String(64))
    requested_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="SET NULL"),
        index=True,
    )
    client_request_id: Mapped[str | None] = mapped_column(String(128))
    failure_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        UniqueConstraint(
            "deliverable_id",
            "version_number",
            name="uq_deliverable_export_version",
        ),
        UniqueConstraint(
            "deliverable_id",
            "snapshot_hash",
            name="uq_deliverable_export_snapshot",
        ),
        UniqueConstraint(
            "requested_by_user_id",
            "client_request_id",
            name="uq_deliverable_export_client_request",
        ),
    )


class DeliverableSection(Base):
    __tablename__ = "deliverable_section"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    deliverable_id: Mapped[str] = mapped_column(String(36), ForeignKey("deliverable.id"), nullable=False)
    section_key: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    assignee_type: Mapped[str] = mapped_column(String(30), nullable=False, default="ai")
    # The reviewed snapshot is distinct from the latest draft. Export must use
    # this immutable pointer rather than whichever version was written last.
    approved_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "section_version.id",
            ondelete="SET NULL",
            name="fk_deliverable_section_approved_version",
            use_alter=True,
        ),
        nullable=True,
        index=True,
    )
    # Outline editor order (OpenBidKit-style chapter board). Lower = earlier.
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    deliverable: Mapped["Deliverable"] = relationship(back_populates="sections")
    versions: Mapped[list["SectionVersion"]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        foreign_keys="SectionVersion.deliverable_section_id",
    )


class ResponsePlan(Base):
    """An immutable structural response-plan revision for one deliverable.

    Requirements and ownership can change as a proposal evolves.  Instead of
    mutating the historical plan used by a draft, a source-fingerprint change
    creates a new revision and supersedes the active one.
    """

    __tablename__ = "response_plan"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    deliverable_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("deliverable.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
        server_default="active",
        index=True,
    )
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # These requirements are intentionally visible as a plan gap instead of
    # being guessed into an unrelated section.
    unmapped_requirement_ids_json: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    created_by_actor: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="workflow",
        server_default="workflow",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    sections: Mapped[list["ResponsePlanSection"]] = relationship(
        back_populates="response_plan",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "deliverable_id",
            "version_number",
            name="uq_response_plan_deliverable_version",
        ),
        Index(
            "ix_response_plan_project_deliverable_status",
            "project_id",
            "deliverable_id",
            "status",
        ),
    )


class ResponsePlanSection(Base):
    """A durable section assignment inside one response-plan revision."""

    __tablename__ = "response_plan_section"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    response_plan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("response_plan.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    deliverable_section_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("deliverable_section.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    section_key: Mapped[str] = mapped_column(String(100), nullable=False)
    title_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order_snapshot: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="planned",
        server_default="planned",
    )

    response_plan: Mapped["ResponsePlan"] = relationship(back_populates="sections")
    requirements: Mapped[list["ResponsePlanRequirement"]] = relationship(
        back_populates="response_plan_section",
        cascade="all, delete-orphan",
    )
    evidence_bindings: Mapped[list["ResponsePlanEvidenceBinding"]] = relationship(
        back_populates="response_plan_section",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "response_plan_id",
            "deliverable_section_id",
            name="uq_response_plan_section",
        ),
    )


class ResponsePlanRequirement(Base):
    """Requirement and owner snapshot assigned to a response-plan section."""

    __tablename__ = "response_plan_requirement"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    response_plan_section_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("response_plan_section.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requirement_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("requirement_item.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    requirement_lock_version: Mapped[int] = mapped_column(Integer, nullable=False)
    requirement_text_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    priority_snapshot: Mapped[str] = mapped_column(String(30), nullable=False)
    owner_user_id_snapshot: Mapped[str | None] = mapped_column(String(36))
    verification_status_snapshot: Mapped[str] = mapped_column(String(30), nullable=False)
    assignment_reason: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="section_key_exact_match",
        server_default="section_key_exact_match",
    )

    response_plan_section: Mapped["ResponsePlanSection"] = relationship(
        back_populates="requirements"
    )

    __table_args__ = (
        UniqueConstraint(
            "response_plan_section_id",
            "requirement_id",
            name="uq_response_plan_section_requirement",
        ),
    )


class ResponsePlanEvidenceBinding(Base):
    """The exact evidence and writing plan used for one draft candidate."""

    __tablename__ = "response_plan_evidence_binding"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    response_plan_section_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("response_plan_section.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_set_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("evidence_set.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    execution_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("execution_run.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    generation_iteration: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    content_plan_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    evidence_set_status: Mapped[str] = mapped_column(String(30), nullable=False)
    unmet_requirement_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    degraded_reasons_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    response_plan_section: Mapped["ResponsePlanSection"] = relationship(
        back_populates="evidence_bindings"
    )

    __table_args__ = (
        UniqueConstraint(
            "execution_run_id",
            "generation_iteration",
            name="uq_response_plan_binding_run_iteration",
        ),
    )


class SectionVersion(Base):
    __tablename__ = "section_version"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    deliverable_section_id: Mapped[str] = mapped_column(String(36), ForeignKey("deliverable_section.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_json: Mapped[dict | None] = mapped_column(JSON)
    content_markdown: Mapped[str | None] = mapped_column(Text)
    created_by_actor: Mapped[str] = mapped_column(String(30), nullable=False, default="ai")
    generation_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("execution_run.id"))
    evidence_set_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("evidence_set.id", ondelete="SET NULL"),
        index=True,
    )
    response_plan_section_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("response_plan_section.id", ondelete="SET NULL"),
        index=True,
    )
    response_plan_evidence_binding_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("response_plan_evidence_binding.id", ondelete="SET NULL"),
        index=True,
    )
    # A single LangGraph run can produce multiple review candidates after a
    # human rejection. Keep the candidate iteration durable so retries are
    # idempotent without collapsing a later revision onto the first version.
    generation_iteration: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    section: Mapped["DeliverableSection"] = relationship(
        back_populates="versions",
        foreign_keys=[deliverable_section_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "deliverable_section_id",
            "generation_run_id",
            "generation_iteration",
            name="uq_section_version_run_iteration",
        ),
    )


class ExecutionRun(Base):
    __tablename__ = "execution_run"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("project.id"), nullable=False)
    parent_execution_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("execution_run.id", ondelete="SET NULL"),
    )
    # Browser and API retries must resolve to the same durable workflow run.
    # It is nullable for historical rows and worker-created recovery attempts.
    requested_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    client_request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    run_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    input_json: Mapped[dict | None] = mapped_column(JSON)
    output_json: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    __table_args__ = (
        UniqueConstraint("parent_execution_run_id", "attempt_number", name="uq_execution_run_parent_attempt"),
        UniqueConstraint(
            "requested_by_user_id",
            "client_request_id",
            name="uq_execution_run_user_client_request",
        ),
        Index("ix_execution_run_request_id", "requested_by_user_id", "client_request_id"),
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
    section_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("section_version.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
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
    parent_event_id: Mapped[str | None] = mapped_column(String(36))
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    public_summary: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.2")
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
    # The action belongs to one durable model-turn event.  This is intentionally
    # separate from the opaque action key so replay can rebuild a public event
    # tree without parsing implementation identifiers.
    parent_event_id: Mapped[str | None] = mapped_column(String(36))
    turn_id: Mapped[str | None] = mapped_column(String(64))
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


class Mem0ProfileSync(Base):
    """Local idempotency/audit ledger for optional Mem0 profile capture."""

    __tablename__ = "mem0_profile_sync"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organization.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), nullable=False)
    runtime_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("runtime_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    conversation_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("chat_conversation.id", ondelete="SET NULL"),
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="mem0_platform")
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="queued")
    external_event_id: Mapped[str | None] = mapped_column(String(160))
    error_code: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("runtime_run_id", "provider", name="uq_mem0_profile_sync_run_provider"),
        Index("ix_mem0_profile_sync_user_status_created", "org_id", "user_id", "status", "created_at"),
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
    source_conversation_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("chat_conversation.id", ondelete="SET NULL"),
    )
    checkpoint_message_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("chat_message.id", ondelete="SET NULL"),
    )
    title: Mapped[str | None] = mapped_column(String(255))
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        foreign_keys="ChatMessage.conversation_id",
    )
    task_state: Mapped["ChatTaskState | None"] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_message"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_conversation.id"), nullable=False)
    runtime_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("runtime_run.id", ondelete="SET NULL"),
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversation: Mapped["ChatConversation"] = relationship(
        back_populates="messages",
        foreign_keys=[conversation_id],
    )
    attachments: Mapped[list["ChatMessageAttachment"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        order_by="ChatMessageAttachment.created_at",
    )


class ChatMessageAttachment(Base):
    """Immutable attachment snapshot belonging to one chat message.

    AssistantAttachment remains a short-lived upload/ingestion record.  A
    conversation needs its own durable snapshot so history and later turns do
    not depend on the browser's staged-attachment list or a temporary object.
    """

    __tablename__ = "chat_message_attachment"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    chat_message_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chat_message.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assistant_attachment_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("assistant_attachment.id", ondelete="SET NULL"),
        index=True,
    )
    document_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("source_document.id", ondelete="SET NULL"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="file")
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False, default="application/octet-stream")
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extraction_status: Mapped[str] = mapped_column(String(30), nullable=False, default="empty")
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    extraction_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    message: Mapped["ChatMessage"] = relationship(back_populates="attachments")


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
