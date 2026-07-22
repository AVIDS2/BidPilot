import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.auth.service import check_plan_limit
from app.db import Base
from app.entitlements.service import (
    EntitlementAccessDenied,
    SeatCapacityExceeded,
    resolve_org_entitlements,
    upsert_organization_subscription_command,
)
from app.models import Organization, OrganizationMembership, Project, Subscription, User
from app.invitations.service import accept_invitation_command, create_invitation_command
from app.organizations.service import create_org_for_user_command
from app.usage.schemas import ProviderSource
from app.usage.service import (
    UsageLimitExceeded,
    check_workflow_quota,
    count_official_workflow_starts,
    get_usage_quota,
    record_usage_event,
)


def _make_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _organization(db: Session, label: str) -> Organization:
    org = Organization(
        slug=f"{label}-{uuid.uuid4().hex[:8]}",
        name=label,
    )
    db.add(org)
    db.flush()
    return org


def _member(
    db: Session,
    *,
    org: Organization,
    role: str = "member",
    active_org_id: str | None = None,
) -> User:
    user = User(
        email=f"{uuid.uuid4().hex}@example.test",
        display_name="Entitlement Test User",
        password_hash="test-only",
        email_verified=True,
        org_id=active_org_id or org.id,
    )
    db.add(user)
    db.flush()
    db.add(OrganizationMembership(org_id=org.id, user_id=user.id, role=role))
    db.flush()
    return user


def _add_membership(db: Session, *, org: Organization, user: User, role: str = "member") -> None:
    db.add(OrganizationMembership(org_id=org.id, user_id=user.id, role=role))
    db.flush()


def test_organization_subscription_overrides_legacy_user_subscription() -> None:
    db = _make_db()
    try:
        org = _organization(db, "Override Org")
        owner = _member(db, org=org, role="owner")
        db.add(Subscription(user_id=owner.id, plan="professional", status="active"))
        upsert_organization_subscription_command(
            db,
            org_id=org.id,
            billing_owner_user_id=owner.id,
            plan="starter",
            seat_limit=3,
        )

        context = resolve_org_entitlements(db, org_id=org.id, actor_user_id=owner.id)

        assert context.source == "organization"
        assert context.plan == "starter"
        assert context.seat_limit == 1
        assert context.is_billing_owner is True
    finally:
        db.close()


def test_inactive_organization_subscription_falls_back_to_starter() -> None:
    db = _make_db()
    try:
        org = _organization(db, "Canceled Org")
        owner = _member(db, org=org, role="owner")
        upsert_organization_subscription_command(
            db,
            org_id=org.id,
            billing_owner_user_id=owner.id,
            plan="professional",
            status="canceled",
            seat_limit=4,
        )

        context = resolve_org_entitlements(db, org_id=org.id, actor_user_id=owner.id)

        assert context.source == "organization"
        assert context.subscription_status == "canceled"
        assert context.plan == "starter"
    finally:
        db.close()


def test_legacy_subscription_only_applies_to_active_organization() -> None:
    db = _make_db()
    try:
        active_org = _organization(db, "Active Org")
        second_org = _organization(db, "Second Org")
        user = _member(db, org=active_org, role="owner")
        _add_membership(db, org=second_org, user=user)
        db.add(Subscription(user_id=user.id, plan="professional", status="active"))
        db.commit()

        active_context = resolve_org_entitlements(
            db,
            org_id=active_org.id,
            actor_user_id=user.id,
        )
        secondary_context = resolve_org_entitlements(
            db,
            org_id=second_org.id,
            actor_user_id=user.id,
        )

        assert active_context.source == "legacy"
        assert active_context.plan == "professional"
        assert secondary_context.source == "starter"
        assert secondary_context.plan == "starter"
    finally:
        db.close()


def test_resolver_rejects_non_member() -> None:
    db = _make_db()
    try:
        member_org = _organization(db, "Member Org")
        other_org = _organization(db, "Other Org")
        user = _member(db, org=member_org, role="owner")
        db.commit()

        with pytest.raises(EntitlementAccessDenied):
            resolve_org_entitlements(db, org_id=other_org.id, actor_user_id=user.id)
    finally:
        db.close()


def test_members_share_official_usage_within_one_organization() -> None:
    db = _make_db()
    try:
        org = _organization(db, "Shared Usage Org")
        owner = _member(db, org=org, role="owner")
        member = _member(db, org=org)
        for _ in range(3):
            record_usage_event(
                db,
                user_id=owner.id,
                org_id=org.id,
                event_type="workflow_draft_started",
                provider_source=ProviderSource.OFFICIAL,
            )
        db.commit()

        quota = get_usage_quota(db, org_id=org.id, actor_user_id=member.id)

        assert quota.monthly_workflow_used == 3
        assert count_official_workflow_starts(db, org.id) == 3
        with pytest.raises(UsageLimitExceeded, match="starter workflow trial limit"):
            check_workflow_quota(db, member.id, org.id, ProviderSource.OFFICIAL)
    finally:
        db.close()


def test_usage_is_isolated_between_organizations_for_same_user() -> None:
    db = _make_db()
    try:
        first_org = _organization(db, "First Usage Org")
        second_org = _organization(db, "Second Usage Org")
        user = _member(db, org=first_org, role="owner")
        _add_membership(db, org=second_org, user=user)
        for _ in range(2):
            record_usage_event(
                db,
                user_id=user.id,
                org_id=first_org.id,
                event_type="workflow_draft_started",
                provider_source=ProviderSource.OFFICIAL,
            )
        record_usage_event(
            db,
            user_id=user.id,
            org_id=second_org.id,
            event_type="workflow_draft_started",
            provider_source=ProviderSource.OFFICIAL,
        )
        db.commit()

        first_quota = get_usage_quota(
            db,
            org_id=first_org.id,
            actor_user_id=user.id,
        )
        second_quota = get_usage_quota(
            db,
            org_id=second_org.id,
            actor_user_id=user.id,
        )

        assert first_quota.monthly_workflow_used == 2
        assert second_quota.monthly_workflow_used == 1
    finally:
        db.close()


def test_project_limit_uses_organization_subscription_not_cached_user_plan() -> None:
    db = _make_db()
    try:
        org = _organization(db, "Professional Org")
        owner = _member(db, org=org, role="owner")
        db.add(Subscription(user_id=owner.id, plan="starter", status="active"))
        upsert_organization_subscription_command(
            db,
            org_id=org.id,
            billing_owner_user_id=owner.id,
            plan="professional",
            seat_limit=3,
        )
        for index in range(5):
            db.add(
                Project(
                    org_id=org.id,
                    slug=f"professional-project-{index}",
                    name=f"Professional Project {index}",
                    scenario_package="bidpilot",
                )
            )
        db.commit()

        check_plan_limit(db, owner.id, "projects", delta=1, org_id=org.id)
    finally:
        db.close()


def test_new_workspace_gets_enforced_starter_capacity() -> None:
    db = _make_db()
    try:
        initial_org = _organization(db, "Initial Workspace")
        user = _member(db, org=initial_org, role="owner")
        db.commit()

        workspace, switched_user = create_org_for_user_command(
            db,
            name="New Workspace",
            slug=f"new-workspace-{uuid.uuid4().hex[:8]}",
            user_id=user.id,
        )
        context = resolve_org_entitlements(
            db,
            org_id=workspace.id,
            actor_user_id=switched_user.id,
        )

        assert context.source == "organization"
        assert context.plan == "starter"
        assert context.seat_limit == 1
        assert context.active_member_count == 1
        assert context.available_seats == 0
        assert context.capacity_enforced is True
    finally:
        db.close()


def test_invitation_acceptance_keeps_pending_state_when_workspace_is_full() -> None:
    db = _make_db()
    try:
        org = _organization(db, "Full Workspace")
        owner = _member(db, org=org, role="owner")
        other_org = _organization(db, "Invitee Home")
        invitee = _member(db, org=other_org, role="owner")
        upsert_organization_subscription_command(
            db,
            org_id=org.id,
            billing_owner_user_id=owner.id,
            plan="starter",
            seat_limit=1,
        )
        invitation = create_invitation_command(db, org.id, invitee.email, owner.id)

        with pytest.raises(SeatCapacityExceeded, match="seat capacity"):
            accept_invitation_command(db, invitation.token, invitee.id)

        db.refresh(invitation)
        assert invitation.status == "pending"
        assert db.query(OrganizationMembership).filter_by(
            org_id=org.id,
            user_id=invitee.id,
        ).first() is None
    finally:
        db.close()


def test_invitation_acceptance_uses_configured_workspace_seats() -> None:
    db = _make_db()
    try:
        org = _organization(db, "Two Seat Workspace")
        owner = _member(db, org=org, role="owner")
        other_org = _organization(db, "Second Invitee Home")
        invitee = _member(db, org=other_org, role="owner")
        upsert_organization_subscription_command(
            db,
            org_id=org.id,
            billing_owner_user_id=owner.id,
            plan="professional",
            seat_limit=2,
        )
        invitation = create_invitation_command(db, org.id, invitee.email, owner.id)

        accepted = accept_invitation_command(db, invitation.token, invitee.id)
        context = resolve_org_entitlements(db, org_id=org.id, actor_user_id=owner.id)

        assert accepted is not None
        assert accepted.status == "accepted"
        assert context.active_member_count == 2
        assert context.available_seats == 0
        assert context.capacity_enforced is True
    finally:
        db.close()


def test_workspace_reports_seat_overage_without_removing_active_members() -> None:
    db = _make_db()
    try:
        org = _organization(db, "Seat Overage Workspace")
        owner = _member(db, org=org, role="owner")
        colleague = _member(db, org=org, role="member")
        upsert_organization_subscription_command(
            db,
            org_id=org.id,
            billing_owner_user_id=owner.id,
            plan="professional",
            seat_limit=2,
        )
        # Simulate a later Stripe Portal quantity decrease. The commercial
        # record must reflect the paid capacity without deleting a collaborator.
        upsert_organization_subscription_command(
            db,
            org_id=org.id,
            billing_owner_user_id=owner.id,
            plan="professional",
            seat_limit=1,
        )

        context = resolve_org_entitlements(db, org_id=org.id, actor_user_id=owner.id)

        assert colleague.id
        assert context.active_member_count == 2
        assert context.seat_limit == 1
        assert context.available_seats == 0
        assert context.seat_overage_count == 1
    finally:
        db.close()


def test_invitation_acceptance_requires_matching_email() -> None:
    db = _make_db()
    try:
        org = _organization(db, "Email Match Workspace")
        owner = _member(db, org=org, role="owner")
        other_org = _organization(db, "Unexpected User Home")
        unexpected_user = _member(db, org=other_org, role="owner")
        invitation = create_invitation_command(
            db,
            org.id,
            "expected@example.test",
            owner.id,
        )

        with pytest.raises(ValueError, match="email"):
            accept_invitation_command(db, invitation.token, unexpected_user.id)

        db.refresh(invitation)
        assert invitation.status == "pending"
    finally:
        db.close()


def test_current_organization_entitlements_endpoint(
    client,
    default_org_id: str,
    default_user_id: str,
) -> None:
    response = client.get("/organizations/current/entitlements")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["org_id"] == default_org_id
    assert body["plan"] in {"starter", "professional", "enterprise"}
    assert body["source"] in {"organization", "legacy", "starter"}
    assert body["seat_limit"] >= 1
    assert body["active_member_count"] >= 1


def test_current_organization_members_endpoint_returns_workspace_roles(
    client,
    default_user_id: str,
) -> None:
    response = client.get("/organizations/current/members")

    assert response.status_code == 200, response.text
    current_member = next(item for item in response.json() if item["id"] == default_user_id)
    assert current_member["role"] == "owner"
    assert current_member["email"]
