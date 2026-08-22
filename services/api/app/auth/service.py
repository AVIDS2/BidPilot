import hashlib
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import NamedTuple

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.entitlements.constants import (
    PLAN_PROJECT_LIMITS,
    VALID_PLANS,
    VALID_SUBSCRIPTION_STATUSES,
)
from app.entitlements.service import EntitlementAccessDenied, resolve_org_entitlements
from app.models import (
    Organization,
    OrganizationMembership,
    OrganizationSubscription,
    Project,
    ProjectMember,
    RefreshToken,
    Mem0ProfileSync,
    Subscription,
    Team,
    TeamMember,
    User,
)
from app.organizations.service import (
    create_personal_organization_command,
    create_organization_membership_command,
)
from app.security.redis_rate_limiter import create_rate_limiter
from app.usage.service import get_user_plan

from .repository import get_user_by_email, get_user_by_id
from .schemas import CurrentUser, TokenResponse, UserRegister, UserUpdate

JWT_SECRET = os.environ.get("DOCPILOT_JWT_SECRET", "dev-secret-change-in-production-32bytes!")
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_HOURS = 24
REFRESH_EXPIRES_DAYS = 7
RESET_EXPIRES_MINUTES = 30
AUTH_REQUIRED = os.environ.get("DOCPILOT_AUTH_REQUIRED", "false").lower() == "true"

PLAN_LIMITS = PLAN_PROJECT_LIMITS

_bearer = HTTPBearer(auto_error=False)


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hash_: str) -> bool:
    return bcrypt.checkpw(password.encode(), hash_.encode())


def _validate_password_strength(password: str) -> None:
    """Raise ValueError if password doesn't meet minimum strength requirements."""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    if not any(c.isupper() for c in password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not any(c.islower() for c in password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not any(c.isdigit() for c in password):
        raise ValueError("Password must contain at least one digit")


def _create_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(UTC) + timedelta(hours=JWT_EXPIRES_HOURS),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _create_refresh_token(user_id: str) -> str:
    import uuid
    payload = {
        "sub": user_id,
        "purpose": "refresh",
        "jti": str(uuid.uuid4()),
        "exp": datetime.now(UTC) + timedelta(days=REFRESH_EXPIRES_DAYS),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _get_user_plan(db: Session, user: User) -> str:
    return get_user_plan(db, user.id)


def _get_org_slug(db: Session, org_id: str) -> str:
    org = db.get(Organization, org_id)
    return org.slug if org else ""


def _user_to_current(db: Session, user: User, plan: str | None = None) -> CurrentUser:
    """Build CurrentUser from a User ORM object."""
    return CurrentUser(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        plan=plan or _get_user_plan(db, user),
        email_verified=user.email_verified,
        disabled=user.disabled,
        org_id=user.org_id,
        org_slug=_get_org_slug(db, user.org_id),
    )


def check_plan_limit(
    db: Session,
    user_id: str,
    resource: str = "projects",
    delta: int = 0,
    plan: str | None = None,
    *,
    org_id: str | None = None,
) -> None:
    """Raise ValueError if the active workspace limit would be exceeded.

    ``plan`` remains accepted for old internal callers but is intentionally
    ignored: browser or cached user state must not determine paid capability.
    """
    # The anonymous local-development fallback is server generated and never
    # available when production authentication is enabled. Keep it unmetered
    # so local demos and tests do not depend on persisted billing fixtures.
    if not AUTH_REQUIRED and user_id == "dev-user":
        return
    user = get_user_by_id(db, user_id)
    if user is None:
        raise ValueError("User not found")
    active_org_id = org_id or user.org_id
    try:
        entitlement = resolve_org_entitlements(
            db,
            org_id=active_org_id,
            actor_user_id=user_id,
        )
    except EntitlementAccessDenied as exc:
        raise ValueError("Organization access denied") from exc
    limit = entitlement.project_limit

    if limit == -1:
        return  # unlimited

    if resource == "projects":
        current_count = db.query(Project).filter_by(
            status="active",
            org_id=active_org_id,
        ).count()
    else:
        current_count = 0

    if current_count + delta > limit:
        raise ValueError(
            f"{entitlement.plan} plan limit of {limit} {resource} would be exceeded. "
            "Upgrade to create more."
        )


def update_subscription_command(
    db: Session,
    user_id: str,
    new_plan: str,
    status: str = "active",
    *,
    stripe_customer_id: str | None = None,
    stripe_subscription_id: str | None = None,
    stripe_state_event_created_at: int | None = None,
    commit: bool = True,
) -> Subscription:
    """Update a local subscription and optionally attach Stripe identifiers.

    Webhook processing passes ``commit=False`` so the subscription mutation and
    its idempotency receipt are committed atomically.
    """
    if new_plan not in VALID_PLANS:
        raise ValueError(f"Invalid plan: {new_plan}. Must be one of {VALID_PLANS}")
    if status not in VALID_SUBSCRIPTION_STATUSES:
        raise ValueError(f"Invalid subscription status: {status}. Must be one of {VALID_SUBSCRIPTION_STATUSES}")
    sub = db.query(Subscription).filter_by(user_id=user_id).first()
    if sub is None:
        sub = Subscription(user_id=user_id, plan=new_plan, status=status)
        db.add(sub)
    else:
        sub.plan = new_plan
        sub.status = status
    if stripe_customer_id:
        sub.stripe_customer_id = stripe_customer_id
    if stripe_subscription_id:
        sub.stripe_subscription_id = stripe_subscription_id
    if stripe_state_event_created_at is not None:
        sub.stripe_state_event_created_at = stripe_state_event_created_at

    if commit:
        db.commit()
        db.refresh(sub)
    else:
        db.flush()
    return sub


def register_user_command(db: Session, payload: UserRegister) -> CurrentUser:
    existing = get_user_by_email(db, payload.email)
    if existing is not None:
        raise ValueError("Email already registered")
    _validate_password_strength(payload.password)

    org_id: str | None = None
    membership_role = "member"
    invitation = None
    created_organization = False
    user_id = str(uuid.uuid4())

    # 1. Invitation token takes highest priority
    if payload.invitation_token:
        from app.models import Invitation as InvitationModel
        invitation = db.query(InvitationModel).filter_by(
            token=payload.invitation_token, status="pending"
        ).first()
        if invitation is not None:
            from datetime import UTC, datetime
            if invitation.expires_at > datetime.now(UTC).replace(tzinfo=None):
                if invitation.email.casefold() != payload.email.strip().casefold():
                    raise ValueError("Invitation email does not match registration email")
                org_id = invitation.org_id
            else:
                invitation.status = "expired"
        if org_id is None:
            raise ValueError("Invalid or expired invitation token")

    # 2. Explicit org creation during registration
    elif payload.org_name and payload.org_slug:
        from app.models import Organization as OrgModel
        existing_org = db.query(OrgModel).filter_by(slug=payload.org_slug).first()
        if existing_org is not None:
            raise ValueError("An organization with this slug already exists")
        org = OrgModel(name=payload.org_name, slug=payload.org_slug)
        db.add(org)
        db.flush()
        org_id = org.id
        membership_role = "owner"
        created_organization = True

    # 3. Standalone accounts get an isolated personal workspace. The legacy
    # default workspace remains only for existing data and bootstrap paths.
    if org_id is None:
        org = create_personal_organization_command(db, user_id=user_id, commit=False)
        org_id = org.id
        membership_role = "owner"
        created_organization = True

    user = User(
        id=user_id,
        email=payload.email,
        display_name=payload.display_name,
        password_hash=_hash_password(payload.password),
        org_id=org_id,
    )
    db.add(user)
    db.flush()
    create_organization_membership_command(
        db,
        org_id=org_id,
        user_id=user.id,
        role=membership_role,
        commit=False,
    )
    if created_organization:
        from app.entitlements.service import upsert_organization_subscription_command

        upsert_organization_subscription_command(
            db,
            org_id=org_id,
            billing_owner_user_id=user.id,
            plan="starter",
            seat_limit=1,
            commit=False,
        )
    if invitation is not None:
        invitation.status = "accepted"
    sub = Subscription(user_id=user.id, plan="starter")
    db.add(sub)
    db.commit()
    db.refresh(user)
    return _user_to_current(db, user, plan="starter")


def _issue_session_tokens(db: Session, user: User) -> TokenResponse:
    """Create a persistent browser session for an authenticated user."""
    if user.disabled:
        raise ValueError("Account is disabled. Contact your administrator.")
    if not user.email_verified:
        raise ValueError("Email not verified. Please check your email and verify your account.")

    refresh_token = _create_refresh_token(user.id)
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=REFRESH_EXPIRES_DAYS),
        )
    )
    db.commit()
    return TokenResponse(
        access_token=_create_token(user.id),
        refresh_token=refresh_token,
    )


def login_command(db: Session, email: str, password: str) -> TokenResponse:
    user = get_user_by_email(db, email)
    if user is None or not _verify_password(password, user.password_hash):
        raise ValueError("Invalid credentials")
    return _issue_session_tokens(db, user)


def update_user_command(db: Session, user_id: str, payload: UserUpdate) -> CurrentUser:
    user = get_user_by_id(db, user_id)
    if user is None:
        raise ValueError("User not found")
    if payload.display_name is not None:
        name = payload.display_name.strip()
        if not name:
            raise ValueError("Display name cannot be empty")
        user.display_name = name
    if payload.new_password is not None:
        if not payload.current_password:
            raise ValueError("Current password is required to set a new password")
        if not _verify_password(payload.current_password, user.password_hash):
            raise ValueError("Current password is incorrect")
        _validate_password_strength(payload.new_password)
        user.password_hash = _hash_password(payload.new_password)
    db.commit()
    db.refresh(user)
    return _user_to_current(db, user)


def delete_user_account_command(db: Session, user_id: str) -> str:
    """Delete an account only when it cannot orphan organization assets.

    Team ownership and billing authority must be transferred explicitly. A
    standalone account can be removed with its empty personal workspace; any
    retained operational records are converted into a clear conflict instead
    of leaking a database foreign-key failure to the client.
    """
    user = get_user_by_id(db, user_id)
    if user is None:
        raise ValueError("User not found")

    email = user.email
    try:
        mem0_org_ids = [
            str(row[0])
            for row in db.query(OrganizationMembership.org_id)
            .filter(
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.status == "active",
            )
            .all()
            if row[0]
        ]
        team_owner_membership = (
            db.query(OrganizationMembership)
            .join(Organization)
            .filter(
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.status == "active",
                OrganizationMembership.role == "owner",
                Organization.workspace_kind == "team",
            )
            .first()
        )
        if team_owner_membership is not None:
            raise ValueError(
                "Transfer ownership of every team workspace before deleting this account"
            )

        team_billing_subscription = (
            db.query(OrganizationSubscription)
            .join(Organization)
            .filter(
                OrganizationSubscription.billing_owner_user_id == user.id,
                Organization.workspace_kind == "team",
            )
            .first()
        )
        if team_billing_subscription is not None:
            raise ValueError(
                "Transfer team billing responsibility before deleting this account"
            )

        personal_workspaces = list(
            db.query(Organization)
            .join(OrganizationMembership)
            .filter(
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.status == "active",
                Organization.workspace_kind == "personal",
            )
            .all()
        )
        for workspace in personal_workspaces:
            active_member_count = (
                db.query(OrganizationMembership)
                .filter(
                    OrganizationMembership.org_id == workspace.id,
                    OrganizationMembership.status == "active",
                )
                .count()
            )
            if active_member_count != 1:
                raise ValueError(
                    "Remove or transfer members from the personal workspace before deleting this account"
                )
            if db.query(Project.id).filter(Project.org_id == workspace.id).first() is not None:
                raise ValueError(
                    "Delete or transfer personal workspace projects before deleting this account"
                )
            if db.query(Team.id).filter(Team.org_id == workspace.id).first() is not None:
                raise ValueError(
                    "Delete or transfer personal workspace teams before deleting this account"
                )

            subscription = (
                db.query(OrganizationSubscription)
                .filter(OrganizationSubscription.org_id == workspace.id)
                .first()
            )
            if subscription is not None and (
                subscription.plan != "starter" or subscription.stripe_subscription_id
            ):
                raise ValueError(
                    "Cancel the personal workspace subscription before deleting this account"
                )

        owned_project_memberships = list(
            db.query(ProjectMember)
            .filter(
                ProjectMember.user_id == user.id,
                ProjectMember.role == "owner",
            )
            .all()
        )
        for membership in owned_project_memberships:
            owner_count = (
                db.query(ProjectMember)
                .filter(
                    ProjectMember.project_id == membership.project_id,
                    ProjectMember.role == "owner",
                )
                .count()
            )
            if owner_count <= 1:
                raise ValueError(
                    "Transfer ownership of every project before deleting this account"
                )

        personal_workspace_ids = [workspace.id for workspace in personal_workspaces]
        db.query(Mem0ProfileSync).filter(Mem0ProfileSync.user_id == user.id).delete(synchronize_session=False)
        db.query(RefreshToken).filter(RefreshToken.user_id == user.id).delete()
        db.query(TeamMember).filter(TeamMember.user_id == user.id).delete()
        db.query(ProjectMember).filter(ProjectMember.user_id == user.id).delete()
        if personal_workspace_ids:
            db.query(OrganizationSubscription).filter(
                OrganizationSubscription.org_id.in_(personal_workspace_ids)
            ).delete(synchronize_session=False)

        db.delete(user)
        db.flush()
        for workspace in personal_workspaces:
            db.delete(workspace)
        db.commit()
        try:
            from app.celery_client import celery

            celery.send_task(
                "worker.delete_mem0_profile",
                args=[user_id, mem0_org_ids],
            )
        except Exception:
            # Account deletion is already committed. The Worker task is
            # retried by operations if the optional external provider is down.
            import logging

            logging.getLogger(__name__).warning(
                "Could not enqueue Mem0 profile deletion for deleted user",
                extra={"user_id": user_id},
                exc_info=True,
            )
    except IntegrityError as exc:
        db.rollback()
        raise ValueError(
            "This account has retained operational records. Export data and contact support for assisted deletion."
        ) from exc
    except Exception:
        db.rollback()
        raise

    return email


def get_current_user_from_token(db: Session, token: str) -> CurrentUser | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            return None
    except jwt.PyJWTError:
        return None
    user = get_user_by_id(db, user_id)
    if user is None:
        return None
    return _user_to_current(db, user)


def get_dev_user() -> CurrentUser:
    """Fallback dev user when no auth middleware is active."""
    return CurrentUser(
        id="dev-user", email="dev@docpilot.local", display_name="Dev User",
        role="admin", plan="professional",
        org_id="00000000-0000-0000-0000-000000000001", org_slug="default",
    )


def create_password_reset_token(db: Session, email: str) -> str | None:
    """Create a password reset token for the given email.

    Returns the token string, or None if no user exists for that email.
    Always returns None silently to avoid user enumeration.
    The caller should return a generic success response regardless.
    """
    user = get_user_by_email(db, email)
    if user is None:
        return None
    payload = {
        "sub": user.id,
        "purpose": "password_reset",
        "exp": datetime.now(UTC) + timedelta(minutes=RESET_EXPIRES_MINUTES),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def confirm_password_reset(db: Session, token: str, new_password: str) -> None:
    """Verify a password reset token and update the user's password.

    Raises ValueError on invalid/expired token or password strength failure.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise ValueError("Invalid or expired reset token")
    if payload.get("purpose") != "password_reset":
        raise ValueError("Invalid reset token")
    user_id = payload.get("sub")
    if user_id is None:
        raise ValueError("Invalid reset token")
    user = get_user_by_id(db, user_id)
    if user is None:
        raise ValueError("User not found")
    _validate_password_strength(new_password)
    user.password_hash = _hash_password(new_password)
    db.commit()


def create_email_verification_token(db: Session, user_id: str) -> str:
    """Create an email verification token for the given user."""
    payload = {
        "sub": user_id,
        "purpose": "email_verification",
        "exp": datetime.now(UTC) + timedelta(hours=24),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_email_command(db: Session, token: str) -> CurrentUser:
    """Verify an email verification token and mark the user as verified."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise ValueError("Invalid or expired verification token")
    if payload.get("purpose") != "email_verification":
        raise ValueError("Invalid verification token")
    user_id = payload.get("sub")
    if user_id is None:
        raise ValueError("Invalid verification token")
    user = get_user_by_id(db, user_id)
    if user is None:
        raise ValueError("User not found")
    user.email_verified = True
    db.commit()
    db.refresh(user)
    return _user_to_current(db, user)


def verify_email_and_create_session_command(db: Session, token: str) -> TokenResponse:
    """Redeem a verified email link for the first browser session.

    The verification link is proof of mailbox control, so requiring the user to
    type the password again only adds a dead-end in the registration flow.
    """
    verified_user = verify_email_command(db, token)
    user = get_user_by_id(db, verified_user.id)
    if user is None:
        raise ValueError("User not found")
    return _issue_session_tokens(db, user)


def refresh_token_command(db: Session, refresh_token: str) -> TokenResponse:
    """Exchange a valid refresh token for a new access + refresh token pair."""
    try:
        payload = jwt.decode(refresh_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise ValueError("Invalid or expired refresh token")
    if payload.get("purpose") != "refresh":
        raise ValueError("Invalid refresh token")
    user_id = payload.get("sub")
    if user_id is None:
        raise ValueError("Invalid refresh token")

    # Validate against DB
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    stored = db.query(RefreshToken).filter_by(token_hash=token_hash).first()
    if stored is None:
        raise ValueError("Refresh token not found")
    if stored.revoked:
        raise ValueError("Refresh token has been revoked")
    if stored.expires_at and stored.expires_at < datetime.now(UTC).replace(tzinfo=None):
        raise ValueError("Refresh token has expired")

    user = get_user_by_id(db, user_id)
    if user is None:
        raise ValueError("User not found")
    if user.disabled:
        raise ValueError("Account is disabled")
    if not user.email_verified:
        raise ValueError("Email not verified")

    # Revoke old token, issue new one
    stored.revoked = True
    new_refresh = _create_refresh_token(user.id)
    new_hash = hashlib.sha256(new_refresh.encode()).hexdigest()
    new_rt = RefreshToken(
        user_id=user.id,
        token_hash=new_hash,
        expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=REFRESH_EXPIRES_DAYS),
    )
    db.add(new_rt)
    db.commit()

    return TokenResponse(
        access_token=_create_token(user.id),
        refresh_token=new_refresh,
    )


def revoke_refresh_token(db: Session, refresh_token: str) -> None:
    """Revoke a refresh token (used on logout)."""
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    stored = db.query(RefreshToken).filter_by(token_hash=token_hash).first()
    if stored:
        stored.revoked = True
        db.commit()


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
    access_token: str | None = Query(default=None),
) -> CurrentUser:
    """Dependency that enforces auth when DOCPILOT_AUTH_REQUIRED=true.

    In dev mode (default), falls back to dev user when no token is provided.
    In production mode, requires a valid Bearer token.

    ``access_token`` query param is accepted for EventSource/SSE clients that
    cannot set Authorization headers (browser EventSource limitation).
    """
    raw_token = credentials.credentials if credentials is not None else None
    if not raw_token and access_token:
        raw_token = access_token.strip() or None

    if raw_token is None:
        if AUTH_REQUIRED:
            raise HTTPException(status_code=401, detail="Authentication required")
        return get_dev_user()

    user = get_current_user_from_token(db, raw_token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


async def get_current_user(current_user: CurrentUser = Depends(require_auth)) -> CurrentUser:
    """Dependency that returns the current authenticated user.

    Relies on require_auth for enforcement; caches the same result within a request.
    """
    return current_user


async def require_admin(current_user: CurrentUser = Depends(require_auth)) -> CurrentUser:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user


class BootstrapAdminResult(NamedTuple):
    user: CurrentUser
    status: str


def bootstrap_admin_command(
    db: Session,
    email: str,
    display_name: str,
    password: str,
    promote: bool = False,
) -> BootstrapAdminResult:
    """Idempotently provision the first admin user for a deployment.

    - if no user exists for `email`: create with role="admin" and return status "created";
    - if a user with role "admin" already exists: return status "already_admin";
    - if a user exists with another role and `promote=True`: promote to admin and return status "promoted";
    - otherwise raise ValueError to avoid silently elevating an existing account.
    """
    existing = get_user_by_email(db, email)
    if existing is None:
        # Platform operators need a workspace boundary as well. Reusing the
        # historical global default org makes every bootstrap admin a member of
        # one shared tenant, corrupts seat counts, and eventually blocks the
        # bootstrap path itself.
        user_id = str(uuid.uuid4())
        org = create_personal_organization_command(db, user_id=user_id, commit=False)
        user = User(
            id=user_id,
            email=email,
            display_name=display_name,
            password_hash=_hash_password(password),
            role="admin",
            email_verified=True,
            org_id=org.id,
        )
        db.add(user)
        db.flush()
        create_organization_membership_command(
            db,
            org_id=org.id,
            user_id=user.id,
            role="owner",
            commit=False,
        )
        from app.entitlements.service import upsert_organization_subscription_command

        upsert_organization_subscription_command(
            db,
            org_id=org.id,
            billing_owner_user_id=user.id,
            plan="professional",
            commit=False,
        )
        sub = Subscription(user_id=user.id, plan="professional")
        db.add(sub)
        db.commit()
        db.refresh(user)
        return BootstrapAdminResult(
            user=_user_to_current(db, user, plan="professional"),
            status="created",
        )

    if existing.role == "admin":
        return BootstrapAdminResult(
            user=_user_to_current(db, existing),
            status="already_admin",
        )

    if not promote:
        raise ValueError(f"User {email} exists but is not an admin; pass promote=True to elevate")

    existing.role = "admin"
    db.commit()
    db.refresh(existing)
    return BootstrapAdminResult(
        user=_user_to_current(db, existing),
        status="promoted",
    )


_redis_url = os.environ.get("DOCPILOT_REDIS_URL")
_requires_distributed_rate_limit = os.environ.get("DOCPILOT_ENV", "").lower() == "production"
login_rate_limiter = create_rate_limiter(
    _redis_url,
    max_attempts=5,
    window_seconds=300,
    prefix="rl:login",
    label="login",
    require_redis=_requires_distributed_rate_limit,
)
resend_rate_limiter = create_rate_limiter(
    _redis_url,
    max_attempts=3,
    window_seconds=3600,
    prefix="rl:resend",
    label="resend",
    require_redis=_requires_distributed_rate_limit,
)
registration_rate_limiter = create_rate_limiter(
    _redis_url,
    max_attempts=5,
    window_seconds=3600,
    prefix="rl:register",
    label="registration",
    require_redis=_requires_distributed_rate_limit,
)
password_reset_rate_limiter = create_rate_limiter(
    _redis_url,
    max_attempts=3,
    window_seconds=3600,
    prefix="rl:password-reset",
    label="password reset",
    require_redis=_requires_distributed_rate_limit,
)


def admin_verify_user_command(db: Session, user_id: str) -> CurrentUser:
    """Admin manually marks a user as email-verified."""
    user = get_user_by_id(db, user_id)
    if user is None:
        raise ValueError("User not found")
    user.email_verified = True
    db.commit()
    db.refresh(user)
    return _user_to_current(db, user)
