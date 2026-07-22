"""Enterprise workspace lifecycle coverage for personal fallback and offboarding."""

from __future__ import annotations

import uuid

import pytest

from app.auth.schemas import UserRegister
from app.auth.service import login_command, register_user_command
from app.entitlements.service import upsert_organization_subscription_command
from app.invitations.service import create_invitation_command
from app.models import (
    Organization,
    OrganizationMembership,
    OrganizationMembershipEvent,
    OrganizationSubscription,
    Project,
    ProjectMember,
    Team,
    TeamMember,
    User,
)
from app.organizations.service import (
    OrganizationMembershipConflict,
    create_org_for_user_command,
    create_organization_membership_command,
    ensure_personal_workspace_for_user_command,
    remove_organization_member_command,
    transfer_organization_billing_owner_command,
    update_organization_membership_role_command,
)


def _suffix() -> str:
    return uuid.uuid4().hex[:10]


def _user(db, *, org_id: str, label: str) -> User:
    suffix = _suffix()
    user = User(
        id=str(uuid.uuid4()),
        org_id=org_id,
        email=f"{label}-{suffix}@example.test",
        display_name=label,
        password_hash="test-only",
        email_verified=True,
    )
    db.add(user)
    db.flush()
    return user


def _team_workspace(db, *, label: str = "Workspace") -> tuple[Organization, User, User]:
    suffix = _suffix()
    org = Organization(
        id=str(uuid.uuid4()),
        slug=f"{label.lower()}-{suffix}",
        name=label,
        workspace_kind="team",
    )
    db.add(org)
    db.flush()
    owner = _user(db, org_id=org.id, label="Owner")
    member = _user(db, org_id=org.id, label="Member")
    db.add_all(
        [
            OrganizationMembership(org_id=org.id, user_id=owner.id, role="owner"),
            OrganizationMembership(org_id=org.id, user_id=member.id, role="member"),
            OrganizationSubscription(
                org_id=org.id,
                billing_owner_user_id=owner.id,
                plan="professional",
                status="active",
                seat_limit=2,
                billable_seat_count=2,
            ),
        ]
    )
    db.commit()
    return org, owner, member


def test_standalone_registration_creates_an_isolated_personal_workspace(test_db) -> None:
    suffix = _suffix()
    registered = register_user_command(
        test_db,
        UserRegister(
            email=f"standalone-{suffix}@example.test",
            display_name="Standalone User",
            password="Test1234",
        ),
    )

    user = test_db.get(User, registered.id)
    assert user is not None
    workspace = test_db.get(Organization, user.org_id)
    assert workspace is not None
    assert workspace.workspace_kind == "personal"
    assert workspace.slug.startswith("personal-")
    membership = test_db.query(OrganizationMembership).filter_by(
        org_id=workspace.id,
        user_id=user.id,
    ).one()
    assert membership.role == "owner"
    assert membership.status == "active"
    subscription = test_db.query(OrganizationSubscription).filter_by(org_id=workspace.id).one()
    assert subscription.plan == "starter"
    assert subscription.billing_owner_user_id == user.id


def test_invited_registration_joins_the_team_without_redundant_personal_workspace(test_db) -> None:
    org, owner, _member = _team_workspace(test_db, label="Invited Team")
    subscription = test_db.query(OrganizationSubscription).filter_by(org_id=org.id).one()
    subscription.seat_limit = 3
    subscription.billable_seat_count = 3
    test_db.commit()
    suffix = _suffix()
    email = f"invitee-{suffix}@example.test"
    invitation = create_invitation_command(test_db, org.id, email, owner.id)

    registered = register_user_command(
        test_db,
        UserRegister(
            email=email,
            display_name="Invited User",
            password="Test1234",
            invitation_token=invitation.token,
        ),
    )

    user = test_db.get(User, registered.id)
    assert user is not None
    assert user.org_id == org.id
    memberships = test_db.query(OrganizationMembership).filter_by(user_id=user.id, status="active").all()
    assert [(membership.org_id, membership.role) for membership in memberships] == [(org.id, "member")]
    personal_workspaces = (
        test_db.query(Organization)
        .join(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user.id,
            Organization.workspace_kind == "personal",
        )
        .all()
    )
    assert personal_workspaces == []


def test_offboarding_revokes_project_and_team_grants_and_provisions_personal_fallback(test_db) -> None:
    org, owner, member = _team_workspace(test_db, label="Offboarding Team")
    project = Project(
        id=str(uuid.uuid4()),
        org_id=org.id,
        slug=f"offboarding-project-{_suffix()}",
        name="Offboarding Project",
        scenario_package="bidpilot",
    )
    team = Team(
        id=str(uuid.uuid4()),
        org_id=org.id,
        slug=f"offboarding-team-{_suffix()}",
        name="Offboarding Team",
    )
    test_db.add_all(
        [
            project,
            team,
            ProjectMember(project_id=project.id, user_id=member.id, role="owner"),
            TeamMember(team_id=team.id, user_id=member.id, role="member"),
        ]
    )
    test_db.commit()

    outcome = remove_organization_member_command(
        test_db,
        org_id=org.id,
        actor_user_id=owner.id,
        target_user_id=member.id,
    )

    assert outcome.personal_workspace_created is True
    assert outcome.active_org.workspace_kind == "personal"
    test_db.refresh(member)
    assert member.org_id == outcome.active_org.id
    source_membership = test_db.query(OrganizationMembership).filter_by(
        org_id=org.id,
        user_id=member.id,
    ).one()
    assert source_membership.status == "removed"
    assert source_membership.removed_at is not None
    assert test_db.query(ProjectMember).filter_by(project_id=project.id, user_id=member.id).count() == 0
    reassigned_owner = test_db.query(ProjectMember).filter_by(project_id=project.id, user_id=owner.id).one()
    assert reassigned_owner.role == "owner"
    assert test_db.query(TeamMember).filter_by(team_id=team.id, user_id=member.id).count() == 0
    audit = test_db.query(OrganizationMembershipEvent).filter_by(
        org_id=org.id,
        target_user_id=member.id,
        event_type="membership.removed",
    ).one()
    assert audit.payload_json == {
            "fallback_org_id": outcome.active_org.id,
            "personal_workspace_created": True,
            "project_ownership_transferred": 1,
            "project_memberships_removed": 1,
        "team_memberships_removed": 1,
    }


def test_offboarding_prefers_existing_personal_workspace_without_creating_another(test_db) -> None:
    org, owner, member = _team_workspace(test_db, label="Existing Personal Fallback")
    personal_workspace, created = ensure_personal_workspace_for_user_command(
        test_db,
        user_id=member.id,
        actor_user_id=member.id,
        reason="test_setup",
    )
    assert created is True
    member.org_id = org.id
    test_db.commit()

    outcome = remove_organization_member_command(
        test_db,
        org_id=org.id,
        actor_user_id=owner.id,
        target_user_id=member.id,
    )

    assert outcome.personal_workspace_created is False
    assert outcome.active_org.id == personal_workspace.id
    test_db.refresh(member)
    assert member.org_id == personal_workspace.id


def test_offboarding_rejects_last_owner_without_mutating_membership(test_db) -> None:
    org, owner, _member = _team_workspace(test_db, label="Last Owner Guard")
    owner_membership = test_db.query(OrganizationMembership).filter_by(
        org_id=org.id,
        user_id=owner.id,
    ).one()

    with pytest.raises(OrganizationMembershipConflict, match="last owner"):
        remove_organization_member_command(
            test_db,
            org_id=org.id,
            actor_user_id=owner.id,
            target_user_id=owner.id,
        )

    test_db.refresh(owner_membership)
    assert owner_membership.status == "active"


def test_self_offboarding_requires_project_owner_reassignment(test_db) -> None:
    org, owner, member = _team_workspace(test_db, label="Self Offboarding Guard")
    update_organization_membership_role_command(
        test_db,
        org_id=org.id,
        actor_user_id=owner.id,
        target_user_id=member.id,
        role="owner",
    )
    project = Project(
        id=str(uuid.uuid4()),
        org_id=org.id,
        slug=f"self-offboarding-project-{_suffix()}",
        name="Self Offboarding Project",
        scenario_package="bidpilot",
    )
    test_db.add_all(
        [
            project,
            ProjectMember(project_id=project.id, user_id=member.id, role="owner"),
        ]
    )
    test_db.commit()

    with pytest.raises(OrganizationMembershipConflict, match="Reassign sole project ownership"):
        remove_organization_member_command(
            test_db,
            org_id=org.id,
            actor_user_id=member.id,
            target_user_id=member.id,
        )

    membership = test_db.query(OrganizationMembership).filter_by(org_id=org.id, user_id=member.id).one()
    assert membership.status == "active"
    assert test_db.query(Organization).filter_by(slug=f"personal-{member.id.replace('-', '')}").count() == 0


def test_billing_owner_must_transfer_before_role_change_or_removal(test_db) -> None:
    org, owner, member = _team_workspace(test_db, label="Billing Transfer Guard")
    update_organization_membership_role_command(
        test_db,
        org_id=org.id,
        actor_user_id=owner.id,
        target_user_id=member.id,
        role="owner",
    )

    with pytest.raises(OrganizationMembershipConflict, match="Transfer billing ownership"):
        update_organization_membership_role_command(
            test_db,
            org_id=org.id,
            actor_user_id=owner.id,
            target_user_id=owner.id,
            role="admin",
        )
    with pytest.raises(OrganizationMembershipConflict, match="Transfer billing ownership"):
        remove_organization_member_command(
            test_db,
            org_id=org.id,
            actor_user_id=member.id,
            target_user_id=owner.id,
        )

    transferred = transfer_organization_billing_owner_command(
        test_db,
        org_id=org.id,
        actor_user_id=owner.id,
        target_user_id=member.id,
    )
    assert transferred.billing_owner_user_id == member.id
    updated = update_organization_membership_role_command(
        test_db,
        org_id=org.id,
        actor_user_id=owner.id,
        target_user_id=owner.id,
        role="admin",
    )
    assert updated.role == "admin"
    event_types = [
        event.event_type
        for event in test_db.query(OrganizationMembershipEvent)
        .filter_by(org_id=org.id)
        .order_by(OrganizationMembershipEvent.created_at)
        .all()
    ]
    assert "billing_owner.transferred" in event_types
    assert "membership.role_changed" in event_types


def test_workspace_member_routes_follow_workspace_authority(test_db, client) -> None:
    suffix = _suffix()
    owner_registration = register_user_command(
        test_db,
        UserRegister(
            email=f"route-owner-{suffix}@example.test",
            display_name="Route Owner",
            password="Test1234",
        ),
    )
    owner = test_db.get(User, owner_registration.id)
    assert owner is not None
    owner.email_verified = True
    test_db.commit()
    workspace, owner = create_org_for_user_command(
        test_db,
        name="Route Workspace",
        slug=f"route-workspace-{suffix}",
        user_id=owner.id,
    )
    upsert_organization_subscription_command(
        test_db,
        org_id=workspace.id,
        billing_owner_user_id=owner.id,
        plan="professional",
        seat_limit=2,
    )

    member_registration = register_user_command(
        test_db,
        UserRegister(
            email=f"route-member-{suffix}@example.test",
            display_name="Route Member",
            password="Test1234",
        ),
    )
    member = test_db.get(User, member_registration.id)
    assert member is not None
    member.email_verified = True
    create_organization_membership_command(
        test_db,
        org_id=workspace.id,
        user_id=member.id,
        role="member",
    )
    test_db.commit()
    token = login_command(test_db, owner.email, "Test1234").access_token
    headers = {"Authorization": f"Bearer {token}"}

    listed = client.get("/organizations/current/members", headers=headers)
    assert listed.status_code == 200, listed.text
    listed_member = next(item for item in listed.json() if item["id"] == member.id)
    assert listed_member["role"] == "member"
    assert listed_member["is_billing_owner"] is False

    promoted = client.patch(
        f"/organizations/current/members/{member.id}",
        json={"role": "owner"},
        headers=headers,
    )
    assert promoted.status_code == 200, promoted.text
    assert promoted.json()["role"] == "owner"

    transferred = client.post(
        "/organizations/current/billing-owner",
        json={"user_id": member.id},
        headers=headers,
    )
    assert transferred.status_code == 200, transferred.text
    assert transferred.json()["is_billing_owner"] is True

    removed = client.delete(
        f"/organizations/current/members/{owner.id}",
        headers=headers,
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["personal_workspace_created"] is False
