import hashlib
import os
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import NamedTuple

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, Subscription, Project, RefreshToken

from .repository import create_user, get_user_by_email, get_user_by_id
from .schemas import CurrentUser, TokenResponse, UserRegister, UserUpdate

JWT_SECRET = os.environ.get("DOCPILOT_JWT_SECRET", "dev-secret-change-in-production-32bytes!")
JWT_ALGORITHM = "HS256"
JWT_EXPIRES_HOURS = 24
REFRESH_EXPIRES_DAYS = 7
RESET_EXPIRES_MINUTES = 30
AUTH_REQUIRED = os.environ.get("DOCPILOT_AUTH_REQUIRED", "false").lower() == "true"

PLAN_LIMITS: dict[str, int] = {
    "starter": 3,
    "professional": -1,
    "enterprise": -1,
}

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
    sub = db.query(Subscription).filter_by(user_id=user.id).first()
    return sub.plan if sub else "starter"


def _user_to_current(db: Session, user: User, plan: str | None = None) -> CurrentUser:
    """Build CurrentUser from a User ORM object."""
    return CurrentUser(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        plan=plan or _get_user_plan(db, user),
        email_verified=user.email_verified,
    )


def check_plan_limit(db: Session, user_id: str, resource: str = "projects", delta: int = 0, plan: str | None = None) -> None:
    """Raise ValueError if the user's plan limit would be exceeded.

    `delta` is the number of new items being added (default 0 = just check current count).
    `plan` overrides the plan lookup (useful when already known from auth context).
    """
    if plan is None:
        sub = db.query(Subscription).filter_by(user_id=user_id).first()
        plan = sub.plan if sub else "starter"
    limit = PLAN_LIMITS.get(plan, PLAN_LIMITS["starter"])

    if limit == -1:
        return  # unlimited

    if resource == "projects":
        current_count = db.query(Project).filter_by(status="active").count()
    else:
        current_count = 0

    if current_count + delta > limit:
        raise ValueError(f"{plan} plan limit of {limit} {resource} would be exceeded. Upgrade to create more.")


VALID_PLANS = {"starter", "professional", "enterprise"}


def update_subscription_command(db: Session, user_id: str, new_plan: str) -> Subscription:
    """Update or create a subscription for the given user. Admin-only in router."""
    if new_plan not in VALID_PLANS:
        raise ValueError(f"Invalid plan: {new_plan}. Must be one of {VALID_PLANS}")
    sub = db.query(Subscription).filter_by(user_id=user_id).first()
    if sub is None:
        sub = Subscription(user_id=user_id, plan=new_plan, status="active")
        db.add(sub)
    else:
        sub.plan = new_plan
    db.commit()
    db.refresh(sub)
    return sub


def register_user_command(db: Session, payload: UserRegister) -> CurrentUser:
    existing = get_user_by_email(db, payload.email)
    if existing is not None:
        raise ValueError("Email already registered")
    _validate_password_strength(payload.password)
    user = User(
        email=payload.email,
        display_name=payload.display_name,
        password_hash=_hash_password(payload.password),
    )
    user = create_user(db, user)
    sub = Subscription(user_id=user.id, plan="starter")
    db.add(sub)
    db.commit()
    return _user_to_current(db, user, plan="starter")


def login_command(db: Session, email: str, password: str) -> TokenResponse:
    user = get_user_by_email(db, email)
    if user is None or not _verify_password(password, user.password_hash):
        raise ValueError("Invalid credentials")
    if user.disabled:
        raise ValueError("Account is disabled. Contact your administrator.")
    if not user.email_verified:
        raise ValueError("Email not verified. Please check your email and verify your account.")
    refresh_token = _create_refresh_token(user.id)
    # Store hashed refresh token in DB for server-side validation
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    rt = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=REFRESH_EXPIRES_DAYS),
    )
    db.add(rt)
    db.commit()
    return TokenResponse(
        access_token=_create_token(user.id),
        refresh_token=refresh_token,
    )


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
    return CurrentUser(id="dev-user", email="dev@docpilot.local", display_name="Dev User", role="admin", plan="professional")


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
) -> CurrentUser:
    """Dependency that enforces auth when DOCPILOT_AUTH_REQUIRED=true.

    In dev mode (default), falls back to dev user when no token is provided.
    In production mode, requires a valid Bearer token.
    """
    if credentials is None:
        if AUTH_REQUIRED:
            raise HTTPException(status_code=401, detail="Authentication required")
        return get_dev_user()

    user = get_current_user_from_token(db, credentials.credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


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
        user = User(
            email=email,
            display_name=display_name,
            password_hash=_hash_password(password),
            role="admin",
            email_verified=True,
        )
        user = create_user(db, user)
        sub = Subscription(user_id=user.id, plan="professional")
        db.add(sub)
        db.commit()
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


class LoginRateLimiter:
    """Simple in-memory rate limiter for login attempts per email."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def check(self, email: str) -> None:
        """Raise ValueError if too many recent login attempts for this email."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        self._attempts[email] = [t for t in self._attempts[email] if t > cutoff]
        if len(self._attempts[email]) >= self.max_attempts:
            raise ValueError(f"Too many login attempts. Please try again in {self.window_seconds // 60} minutes.")
        self._attempts[email].append(now)

    def reset(self, email: str) -> None:
        """Clear attempt history for a successful login."""
        self._attempts.pop(email, None)


class ResendRateLimiter:
    """Rate limiter for email verification resend requests per email."""

    def __init__(self, max_attempts: int = 3, window_seconds: int = 3600) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def check(self, email: str) -> None:
        """Raise ValueError if too many recent resend attempts for this email."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        self._attempts[email] = [t for t in self._attempts[email] if t > cutoff]
        if len(self._attempts[email]) >= self.max_attempts:
            raise ValueError(f"Too many verification emails sent. Please try again in {self.window_seconds // 60} minutes.")
        self._attempts[email].append(now)


login_rate_limiter = LoginRateLimiter()
resend_rate_limiter = ResendRateLimiter()


def admin_verify_user_command(db: Session, user_id: str) -> CurrentUser:
    """Admin manually marks a user as email-verified."""
    user = get_user_by_id(db, user_id)
    if user is None:
        raise ValueError("User not found")
    user.email_verified = True
    db.commit()
    db.refresh(user)
    return _user_to_current(db, user)
