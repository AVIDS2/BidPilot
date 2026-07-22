"""Organization workspace, membership, and commercial-authority commands."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

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


MEMBERSHIP_ROLES = {"owner", "admin", "member"}
MEMBERSHIP_MANAGERS = {"owner", "admin"}
ACTIVE_MEMBERSHIP_STATUS = "active"
REMOVED_MEMBERSHIP_STATUS = "removed"
PERSONAL_WORKSPACE_KIND = "personal"
TEAM_WORKSPACE_KIND = "team"
WORKSPACE_KINDS = {PERSONAL_WORKSPACE_KIND, TEAM_WORKSPACE_KIND}


class OrganizationMembershipNotFound(LookupError):
    """Raised when a requested active workspace member does not exist."""


class OrganizationMembershipConflict(ValueError):
    """Raised when a safe workspace-membership transition is impossible."""


@dataclass(frozen=True)
class OrganizationMembershipRemovalOutcome:
    user_id: str
    active_org: Organization
    personal_workspace_created: bool


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _lock_organization(db: Session, org_id: str) -> Organization:
    organization = db.scalar(
        select(Organization).where(Organization.id == org_id).with_for_update()
    )
    if organization is None:
        raise ValueError("Organization not found")
    return organization


def _locked_active_membership(
    db: Session,
    *,
    org_id: str,
    user_id: str,
) -> OrganizationMembership | None:
    return db.scalar(
        select(OrganizationMembership)
        .where(
            OrganizationMembership.org_id == org_id,
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == ACTIVE_MEMBERSHIP_STATUS,
        )
        .with_for_update()
    )


def _locked_workspace_manager(
    db: Session,
    *,
    org_id: str,
    user_id: str,
) -> OrganizationMembership:
    membership = _locked_active_membership(db, org_id=org_id, user_id=user_id)
    if membership is None or membership.role not in MEMBERSHIP_MANAGERS:
        raise PermissionError("Organization manager role required")
    return membership


def _record_membership_event(
    db: Session,
    *,
    org_id: str,
    membership_id: str | None,
    actor_user_id: str | None,
    target_user_id: str | None,
    event_type: str,
    payload: dict | None = None,
) -> OrganizationMembershipEvent:
    event = OrganizationMembershipEvent(
        org_id=org_id,
        membership_id=membership_id,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        event_type=event_type,
        payload_json=payload,
    )
    db.add(event)
    db.flush()
    return event


def create_org_command(
    db: Session,
    name: str,
    slug: str,
    *,
    workspace_kind: str = TEAM_WORKSPACE_KIND,
    commit: bool = True,
) -> Organization:
    if workspace_kind not in WORKSPACE_KINDS:
        raise ValueError("Invalid workspace kind")
    existing = db.scalar(select(Organization).where(Organization.slug == slug))
    if existing is not None:
        raise ValueError("An organization with this slug already exists")
    org = Organization(name=name, slug=slug, workspace_kind=workspace_kind)
    db.add(org)
    if commit:
        db.commit()
        db.refresh(org)
    else:
        db.flush()
    return org


def personal_workspace_slug(user_id: str) -> str:
    """Use a stable non-PII identifier so retrying provisioning is idempotent."""
    return f"personal-{user_id.replace('-', '')}"


def create_personal_organization_command(
    db: Session,
    *,
    user_id: str,
    commit: bool = True,
) -> Organization:
    slug = personal_workspace_slug(user_id)
    existing = db.scalar(select(Organization).where(Organization.slug == slug))
    if existing is not None:
        if existing.workspace_kind != PERSONAL_WORKSPACE_KIND:
            raise OrganizationMembershipConflict("Personal workspace slug is unavailable")
        return existing
    return create_org_command(
        db,
        name="Personal Workspace",
        slug=slug,
        workspace_kind=PERSONAL_WORKSPACE_KIND,
        commit=commit,
    )


def get_active_membership(
    db: Session,
    *,
    org_id: str,
    user_id: str,
) -> OrganizationMembership | None:
    return db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.org_id == org_id,
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == ACTIVE_MEMBERSHIP_STATUS,
        )
    )


def has_active_org_owner(db: Session, org_id: str) -> bool:
    return (
        db.scalar(
            select(OrganizationMembership.id).where(
                OrganizationMembership.org_id == org_id,
                OrganizationMembership.status == ACTIVE_MEMBERSHIP_STATUS,
                OrganizationMembership.role == "owner",
            )
        )
        is not None
    )


def require_organization_role(
    db: Session,
    *,
    org_id: str,
    user_id: str,
    allowed_roles: set[str] | frozenset[str],
) -> OrganizationMembership:
    membership = get_active_membership(db, org_id=org_id, user_id=user_id)
    if membership is None or membership.role not in allowed_roles:
        raise PermissionError("Organization role required")
    return membership


def create_organization_membership_command(
    db: Session,
    *,
    org_id: str,
    user_id: str,
    role: str,
    commit: bool = True,
) -> OrganizationMembership:
    """Create or reactivate one durable membership without changing active org."""
    if role not in MEMBERSHIP_ROLES:
        raise ValueError(f"Invalid organization membership role: {role}")
    if db.get(Organization, org_id) is None:
        raise ValueError("Organization not found")
    if db.get(User, user_id) is None:
        raise ValueError("User not found")

    membership = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.org_id == org_id,
            OrganizationMembership.user_id == user_id,
        )
    )
    if membership is None:
        from app.entitlements.service import ensure_organization_seat_available

        ensure_organization_seat_available(db, org_id=org_id)
        membership = OrganizationMembership(org_id=org_id, user_id=user_id, role=role)
        db.add(membership)
    elif membership.status == REMOVED_MEMBERSHIP_STATUS:
        from app.entitlements.service import ensure_organization_seat_available

        ensure_organization_seat_available(db, org_id=org_id)
        membership.role = role
        membership.status = ACTIVE_MEMBERSHIP_STATUS
        membership.removed_at = None
    else:
        return membership

    if commit:
        db.commit()
        db.refresh(membership)
    else:
        db.flush()
    return membership


def _active_personal_workspace(db: Session, *, user_id: str) -> Organization | None:
    return db.scalar(
        select(Organization)
        .join(OrganizationMembership)
        .where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == ACTIVE_MEMBERSHIP_STATUS,
            Organization.workspace_kind == PERSONAL_WORKSPACE_KIND,
        )
        .order_by(Organization.created_at, Organization.id)
    )


def ensure_personal_workspace_for_user_command(
    db: Session,
    *,
    user_id: str,
    actor_user_id: str | None,
    reason: str,
    commit: bool = True,
) -> tuple[Organization, bool]:
    """Return a safe landing workspace, provisioning it atomically if needed."""
    user = db.get(User, user_id)
    if user is None:
        raise ValueError("User not found")

    workspace = _active_personal_workspace(db, user_id=user_id)
    created = False
    if workspace is None:
        existing_workspace = db.scalar(
            select(Organization).where(Organization.slug == personal_workspace_slug(user_id))
        )
        workspace = create_personal_organization_command(
            db,
            user_id=user_id,
            commit=False,
        )
        created = existing_workspace is None
        membership = create_organization_membership_command(
            db,
            org_id=workspace.id,
            user_id=user_id,
            role="owner",
            commit=False,
        )
        from app.entitlements.service import upsert_organization_subscription_command

        upsert_organization_subscription_command(
            db,
            org_id=workspace.id,
            billing_owner_user_id=user_id,
            plan="starter",
            seat_limit=1,
            commit=False,
        )
        _record_membership_event(
            db,
            org_id=workspace.id,
            membership_id=membership.id,
            actor_user_id=actor_user_id,
            target_user_id=user_id,
            event_type="workspace.personal_provisioned",
            payload={"reason": reason},
        )

    if commit:
        db.commit()
        db.refresh(workspace)
    else:
        db.flush()
    return workspace, created


def create_org_for_user_command(
    db: Session,
    *,
    name: str,
    slug: str,
    user_id: str,
) -> tuple[Organization, User]:
    """Create a team workspace and its owner membership atomically."""
    org = create_org_command(db, name, slug, workspace_kind=TEAM_WORKSPACE_KIND, commit=False)
    create_organization_membership_command(
        db,
        org_id=org.id,
        user_id=user_id,
        role="owner",
        commit=False,
    )
    from app.entitlements.service import upsert_organization_subscription_command

    upsert_organization_subscription_command(
        db,
        org_id=org.id,
        billing_owner_user_id=user_id,
        plan="starter",
        seat_limit=1,
        commit=False,
    )
    user = switch_user_org_command(db, user_id, org.id, commit=False)
    db.commit()
    db.refresh(org)
    db.refresh(user)
    return org, user


def list_user_orgs_query(db: Session, user_id: str) -> list[Organization]:
    """Return active organization memberships, not a mutable user pointer."""
    return list(
        db.scalars(
            select(Organization)
            .join(OrganizationMembership)
            .where(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.status == ACTIVE_MEMBERSHIP_STATUS,
            )
            .order_by(Organization.workspace_kind, Organization.name, Organization.slug, Organization.id)
        ).all()
    )


def list_org_members_query(db: Session, org_id: str) -> list[tuple[OrganizationMembership, User]]:
    return list(
        db.execute(
            select(OrganizationMembership, User)
            .join(User, User.id == OrganizationMembership.user_id)
            .where(
                OrganizationMembership.org_id == org_id,
                OrganizationMembership.status == ACTIVE_MEMBERSHIP_STATUS,
                User.disabled.is_(False),
            )
            .order_by(User.display_name, User.email, User.id)
        ).all()
    )


def get_org_by_id(db: Session, org_id: str) -> Organization | None:
    return db.get(Organization, org_id)


def switch_user_org_command(
    db: Session,
    user_id: str,
    org_id: str,
    *,
    commit: bool = True,
) -> User:
    """Switch active organization only when the user has active membership."""
    if db.get(Organization, org_id) is None:
        raise ValueError("Organization not found")
    user = db.get(User, user_id)
    if user is None:
        raise ValueError("User not found")
    if get_active_membership(db, org_id=org_id, user_id=user_id) is None:
        raise PermissionError("Organization access denied")

    user.org_id = org_id
    if commit:
        db.commit()
        db.refresh(user)
    else:
        db.flush()
    return user


def _fallback_workspace_for_user(
    db: Session,
    *,
    user_id: str,
    excluded_org_id: str,
) -> Organization | None:
    personal_workspace = db.scalar(
        select(Organization)
        .join(OrganizationMembership)
        .where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == ACTIVE_MEMBERSHIP_STATUS,
            OrganizationMembership.org_id != excluded_org_id,
            Organization.workspace_kind == PERSONAL_WORKSPACE_KIND,
        )
        .order_by(Organization.created_at, Organization.id)
    )
    if personal_workspace is not None:
        return personal_workspace
    return db.scalar(
        select(Organization)
        .join(OrganizationMembership)
        .where(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == ACTIVE_MEMBERSHIP_STATUS,
            OrganizationMembership.org_id != excluded_org_id,
        )
        .order_by(Organization.created_at, Organization.id)
    )


def _reassign_sole_project_ownership(
    db: Session,
    *,
    org_id: str,
    actor_user_id: str,
    target_user_id: str,
) -> int:
    """Give the removing manager ownership of projects that would be orphaned."""
    target_project_memberships = list(
        db.scalars(
            select(ProjectMember)
            .join(Project, Project.id == ProjectMember.project_id)
            .where(
                Project.org_id == org_id,
                ProjectMember.user_id == target_user_id,
                ProjectMember.role == "owner",
            )
            .with_for_update()
        ).all()
    )
    transferred = 0
    for target_project_membership in target_project_memberships:
        project_id = target_project_membership.project_id
        other_owner_exists = db.scalar(
            select(ProjectMember.id)
            .where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id != target_user_id,
                ProjectMember.role == "owner",
            )
            .with_for_update()
        )
        if other_owner_exists is not None:
            continue
        if actor_user_id == target_user_id:
            raise OrganizationMembershipConflict(
                "Reassign sole project ownership before leaving this workspace"
            )
        actor_project_membership = db.scalar(
            select(ProjectMember)
            .where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == actor_user_id,
            )
            .with_for_update()
        )
        if actor_project_membership is None:
            db.add(
                ProjectMember(
                    project_id=project_id,
                    user_id=actor_user_id,
                    role="owner",
                )
            )
        elif actor_project_membership.role != "owner":
            actor_project_membership.role = "owner"
        transferred += 1
    db.flush()
    return transferred


def update_organization_membership_role_command(
    db: Session,
    *,
    org_id: str,
    actor_user_id: str,
    target_user_id: str,
    role: str,
    commit: bool = True,
) -> OrganizationMembership:
    """Change a workspace role without allowing ownership or billing orphaning."""
    if role not in MEMBERSHIP_ROLES:
        raise ValueError("Invalid organization membership role")
    _lock_organization(db, org_id)
    actor_membership = _locked_workspace_manager(db, org_id=org_id, user_id=actor_user_id)
    if actor_membership.role != "owner":
        raise PermissionError("Organization owner role required")
    target_membership = _locked_active_membership(db, org_id=org_id, user_id=target_user_id)
    if target_membership is None:
        raise OrganizationMembershipNotFound("Organization member not found")
    if target_membership.role == role:
        return target_membership

    subscription = db.scalar(
        select(OrganizationSubscription)
        .where(OrganizationSubscription.org_id == org_id)
        .with_for_update()
    )
    if subscription is not None and subscription.billing_owner_user_id == target_user_id and role != "owner":
        raise OrganizationMembershipConflict(
            "Transfer billing ownership before changing this member from owner"
        )
    if target_membership.role == "owner" and role != "owner":
        owners = list(
            db.scalars(
                select(OrganizationMembership)
                .where(
                    OrganizationMembership.org_id == org_id,
                    OrganizationMembership.status == ACTIVE_MEMBERSHIP_STATUS,
                    OrganizationMembership.role == "owner",
                )
                .with_for_update()
            ).all()
        )
        if len(owners) <= 1:
            raise OrganizationMembershipConflict("Transfer ownership before removing the last owner")

    previous_role = target_membership.role
    target_membership.role = role
    _record_membership_event(
        db,
        org_id=org_id,
        membership_id=target_membership.id,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        event_type="membership.role_changed",
        payload={"from_role": previous_role, "to_role": role},
    )
    if commit:
        db.commit()
        db.refresh(target_membership)
    else:
        db.flush()
    return target_membership


def transfer_organization_billing_owner_command(
    db: Session,
    *,
    org_id: str,
    actor_user_id: str,
    target_user_id: str,
    commit: bool = True,
) -> OrganizationSubscription:
    """Transfer local billing authority only between active workspace owners."""
    _lock_organization(db, org_id)
    actor_membership = _locked_workspace_manager(db, org_id=org_id, user_id=actor_user_id)
    if actor_membership.role != "owner":
        raise PermissionError("Organization owner role required")
    target_membership = _locked_active_membership(db, org_id=org_id, user_id=target_user_id)
    if target_membership is None or target_membership.role != "owner":
        raise OrganizationMembershipConflict("Billing owner must be an active organization owner")
    subscription = db.scalar(
        select(OrganizationSubscription)
        .where(OrganizationSubscription.org_id == org_id)
        .with_for_update()
    )
    if subscription is None:
        raise OrganizationMembershipConflict("Organization billing is not configured")
    if subscription.billing_owner_user_id != actor_user_id:
        raise PermissionError("Only the current billing owner can transfer billing ownership")
    if subscription.billing_owner_user_id == target_user_id:
        return subscription

    previous_owner_user_id = subscription.billing_owner_user_id
    subscription.billing_owner_user_id = target_user_id
    _record_membership_event(
        db,
        org_id=org_id,
        membership_id=target_membership.id,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        event_type="billing_owner.transferred",
        payload={"from_user_id": previous_owner_user_id},
    )
    if commit:
        db.commit()
        db.refresh(subscription)
    else:
        db.flush()
    return subscription


def remove_organization_member_command(
    db: Session,
    *,
    org_id: str,
    actor_user_id: str,
    target_user_id: str,
    commit: bool = True,
) -> OrganizationMembershipRemovalOutcome:
    """Remove a member without leaving its account or grants in an invalid state."""
    _lock_organization(db, org_id)
    actor_membership = _locked_workspace_manager(db, org_id=org_id, user_id=actor_user_id)
    target_membership = _locked_active_membership(db, org_id=org_id, user_id=target_user_id)
    if target_membership is None:
        raise OrganizationMembershipNotFound("Organization member not found")
    if actor_membership.role == "admin" and target_membership.role == "owner":
        raise PermissionError("Only an organization owner can remove an owner")

    owners = list(
        db.scalars(
            select(OrganizationMembership)
            .where(
                OrganizationMembership.org_id == org_id,
                OrganizationMembership.status == ACTIVE_MEMBERSHIP_STATUS,
                OrganizationMembership.role == "owner",
            )
            .with_for_update()
        ).all()
    )
    if target_membership.role == "owner" and len(owners) <= 1:
        raise OrganizationMembershipConflict("Transfer ownership before removing the last owner")

    subscription = db.scalar(
        select(OrganizationSubscription)
        .where(OrganizationSubscription.org_id == org_id)
        .with_for_update()
    )
    if subscription is not None and subscription.billing_owner_user_id == target_user_id:
        raise OrganizationMembershipConflict(
            "Transfer billing ownership before removing the billing owner"
        )

    target_user = db.scalar(select(User).where(User.id == target_user_id).with_for_update())
    if target_user is None:
        raise OrganizationMembershipNotFound("Organization member not found")
    project_ownership_transferred = _reassign_sole_project_ownership(
        db,
        org_id=org_id,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
    )
    fallback_org = _fallback_workspace_for_user(
        db,
        user_id=target_user_id,
        excluded_org_id=org_id,
    )
    personal_workspace_created = False
    if fallback_org is None:
        fallback_org, personal_workspace_created = ensure_personal_workspace_for_user_command(
            db,
            user_id=target_user_id,
            actor_user_id=actor_user_id,
            reason="member_offboarding",
            commit=False,
        )

    project_memberships_removed = db.execute(
        delete(ProjectMember).where(
            ProjectMember.user_id == target_user_id,
            ProjectMember.project_id.in_(select(Project.id).where(Project.org_id == org_id)),
        )
    ).rowcount or 0
    team_memberships_removed = db.execute(
        delete(TeamMember).where(
            TeamMember.user_id == target_user_id,
            TeamMember.team_id.in_(select(Team.id).where(Team.org_id == org_id)),
        )
    ).rowcount or 0

    target_membership.status = REMOVED_MEMBERSHIP_STATUS
    target_membership.removed_at = _utcnow()
    if target_user.org_id == org_id:
        target_user.org_id = fallback_org.id
    _record_membership_event(
        db,
        org_id=org_id,
        membership_id=target_membership.id,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        event_type="membership.removed",
        payload={
            "fallback_org_id": fallback_org.id,
            "personal_workspace_created": personal_workspace_created,
            "project_ownership_transferred": project_ownership_transferred,
            "project_memberships_removed": project_memberships_removed,
            "team_memberships_removed": team_memberships_removed,
        },
    )
    if commit:
        db.commit()
        db.refresh(fallback_org)
    else:
        db.flush()
    return OrganizationMembershipRemovalOutcome(
        user_id=target_user_id,
        active_org=fallback_org,
        personal_workspace_created=personal_workspace_created,
    )
