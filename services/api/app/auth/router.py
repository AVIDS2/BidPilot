from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.email.service import send_password_reset_email, send_email_verification_email, send_account_deletion_confirmation_email
from app.models import Subscription, User

import math
from .schemas import CurrentUser, TokenResponse, UserLogin, UserRegister, UserUpdate, SubscriptionRead, SubscriptionUpdate, PasswordResetRequest, PasswordResetConfirm, UsersPaginatedResponse
from .service import get_current_user_from_token, get_dev_user, login_command, register_user_command, update_user_command, update_subscription_command, _get_user_plan, _user_to_current, require_admin, create_password_reset_token, confirm_password_reset, create_email_verification_token, verify_email_command, refresh_token_command, login_rate_limiter, resend_rate_limiter, admin_verify_user_command

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


@router.post("/register", response_model=CurrentUser, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)) -> CurrentUser:
    try:
        user = register_user_command(db, payload)
        # Send verification email (async-safe: logs to console if SMTP not configured)
        token = create_email_verification_token(db, user.id)
        send_email_verification_email(payload.email, token)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        login_rate_limiter.check(payload.email)
        result = login_command(db, payload.email, payload.password)
        login_rate_limiter.reset(payload.email)
        return result
    except ValueError as e:
        msg = str(e)
        if "disabled" in msg.lower():
            raise HTTPException(status_code=403, detail=msg)
        if "not verified" in msg.lower():
            raise HTTPException(status_code=403, detail={"error": "email_not_verified", "message": msg, "email": payload.email})
        if "too many" in msg.lower():
            raise HTTPException(status_code=429, detail=msg)
        raise HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(refresh_token: str, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        return refresh_token_command(db, refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/me", response_model=CurrentUser)
def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> CurrentUser:
    if credentials is None:
        return get_dev_user()
    user = get_current_user_from_token(db, credentials.credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


@router.patch("/me", response_model=CurrentUser)
def update_current_user(
    payload: UserUpdate,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> CurrentUser:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = get_current_user_from_token(db, credentials.credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        return update_user_command(db, user.id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/subscription", response_model=SubscriptionRead)
def get_subscription(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> SubscriptionRead:
    if credentials is None:
        return SubscriptionRead(plan="professional", status="active", stripe_customer_id=None)
    user = get_current_user_from_token(db, credentials.credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    sub = db.query(Subscription).filter_by(user_id=user.id).first()
    if sub is None:
        return SubscriptionRead(plan="starter", status="active", stripe_customer_id=None)
    return SubscriptionRead(plan=sub.plan, status=sub.status, stripe_customer_id=sub.stripe_customer_id)


@router.patch("/subscription", response_model=SubscriptionRead)
def update_subscription(
    payload: SubscriptionUpdate,
    admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SubscriptionRead:
    try:
        sub = update_subscription_command(db, payload.user_id, payload.plan)
        return SubscriptionRead(plan=sub.plan, status=sub.status, stripe_customer_id=sub.stripe_customer_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Admin user management ---

@router.get("/users", response_model=UsersPaginatedResponse)
def list_users(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UsersPaginatedResponse:
    total = db.query(User).count()
    users = (
        db.query(User)
        .order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return UsersPaginatedResponse(
        items=[_user_to_current(db, u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)) if total > 0 else 1,
    )


@router.patch("/users/{user_id}", response_model=CurrentUser)
def update_user_admin(
    user_id: str,
    payload: UserUpdate,
    admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CurrentUser:
    try:
        return update_user_command(db, user_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/users/{user_id}/role", response_model=CurrentUser)
def update_user_role(
    user_id: str,
    role: str,
    admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CurrentUser:
    if role not in ("admin", "member"):
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'member'")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = role
    db.commit()
    db.refresh(user)
    return _user_to_current(db, user)


@router.patch("/users/{user_id}/status", response_model=CurrentUser)
def toggle_user_status(
    user_id: str,
    disabled: bool,
    admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CurrentUser:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.disabled = disabled
    db.commit()
    db.refresh(user)
    return _user_to_current(db, user)


@router.post("/password-reset")
def request_password_reset(payload: PasswordResetRequest, db: Session = Depends(get_db)) -> dict:
    """Request a password reset. Always returns success to avoid user enumeration.

    If the email exists, a reset link is sent. If SMTP is not configured,
    the token is logged to console for development.
    """
    token = create_password_reset_token(db, payload.email)
    if token is not None:
        send_password_reset_email(payload.email, token)
    return {"message": "If an account exists for that email, a reset link has been sent."}


@router.post("/password-reset/confirm")
def confirm_reset(payload: PasswordResetConfirm, db: Session = Depends(get_db)) -> dict:
    try:
        confirm_password_reset(db, payload.token, payload.new_password)
        return {"message": "Password has been reset successfully."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Email verification ---

@router.post("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)) -> dict:
    try:
        verify_email_command(db, token)
        return {"message": "Email verified successfully."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/resend-verification")
def resend_verification(
    email: str = Query("", description="Email address to resend verification to"),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> dict:
    """Resend email verification. Accepts either a Bearer token or an email query param.

    Rate-limited to 3 resends per email per hour.
    """
    target_email = email
    target_user_id: str | None = None

    if credentials is not None:
        user = get_current_user_from_token(db, credentials.credentials)
        if user is not None:
            target_email = user.email
            target_user_id = user.id

    if not target_email:
        raise HTTPException(status_code=400, detail="Email or Bearer token required")

    try:
        resend_rate_limiter.check(target_email)
    except ValueError as e:
        raise HTTPException(status_code=429, detail=str(e))

    if target_user_id is None:
        orm_user = db.query(User).filter_by(email=target_email).first()
        if orm_user is None:
            # Don't reveal whether email exists
            return {"message": "If the account exists and is unverified, a verification email has been sent."}
        target_user_id = orm_user.id

    orm = db.get(User, target_user_id)
    if orm is None or orm.email_verified:
        return {"message": "If the account exists and is unverified, a verification email has been sent."}

    token = create_email_verification_token(db, target_user_id)
    send_email_verification_email(target_email, token)
    return {"message": "If the account exists and is unverified, a verification email has been sent."}


@router.post("/users/{user_id}/verify", response_model=CurrentUser)
def admin_verify_user(
    user_id: str,
    admin: CurrentUser = Depends(require_admin),
    db: Session = Depends(get_db),
) -> CurrentUser:
    """Admin manually marks a user's email as verified."""
    try:
        return admin_verify_user_command(db, user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Account deletion & data export ---

@router.delete("/me")
def delete_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> dict:
    """Delete the current user's account and all associated data."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = get_current_user_from_token(db, credentials.credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    # Prevent admins from deleting themselves if they're the only admin
    if user.role == "admin":
        admin_count = db.query(User).filter(User.role == "admin", User.disabled == False).count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last admin account. Promote another user first.")
    orm_user = db.get(User, user.id)
    if orm_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    email = orm_user.email
    # Clean up refresh tokens before deleting user (FK constraint)
    from app.models import RefreshToken
    db.query(RefreshToken).filter(RefreshToken.user_id == orm_user.id).delete()
    db.delete(orm_user)
    db.commit()
    send_account_deletion_confirmation_email(email)
    return {"message": "Account deleted successfully."}


@router.get("/me/export")
def export_user_data(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> dict:
    """Export all data associated with the current user (GDPR compliance)."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = get_current_user_from_token(db, credentials.credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    from app.models import (
        Project, Bundle, SourceDocument, Deliverable, DeliverableSection,
        RequirementItem, Evidence, ExecutionRun, ReviewComment, ReviewThread,
        AuditEvent, SectionVersion,
    )

    # Find all projects this user has interacted with
    audit_project_ids = [
        row[0] for row in db.query(AuditEvent.project_id)
        .filter(AuditEvent.actor_id == user.id)
        .distinct()
        .all()
    ]

    data: dict[str, list] = {
        "account": [{"id": user.id, "email": user.email, "display_name": user.display_name, "role": user.role}],
        "projects": [
            {"id": p.id, "name": p.name, "slug": p.slug, "status": p.status, "scenario_package": p.scenario_package}
            for p in db.query(Project).filter(Project.id.in_(audit_project_ids)).all()
        ] if audit_project_ids else [],
        "bundles": [
            {"id": b.id, "project_id": b.project_id, "label": b.label, "source_type": b.source_type, "ingest_status": b.ingest_status}
            for b in db.query(Bundle).filter(Bundle.project_id.in_(audit_project_ids)).all()
        ] if audit_project_ids else [],
        "documents": [
            {"id": d.id, "bundle_id": d.bundle_id, "original_filename": d.original_filename, "mime_type": d.mime_type, "parse_status": d.parse_status}
            for d in db.query(SourceDocument).join(Bundle).filter(Bundle.project_id.in_(audit_project_ids)).all()
        ] if audit_project_ids else [],
        "deliverables": [
            {"id": d.id, "project_id": d.project_id, "type": d.type, "title": d.title, "status": d.status, "export_status": d.export_status}
            for d in db.query(Deliverable).filter(Deliverable.project_id.in_(audit_project_ids)).all()
        ] if audit_project_ids else [],
        "sections": [
            {"id": s.id, "deliverable_id": s.deliverable_id, "section_key": s.section_key, "title": s.title, "status": s.status}
            for s in db.query(DeliverableSection).join(Deliverable).filter(Deliverable.project_id.in_(audit_project_ids)).all()
        ] if audit_project_ids else [],
        "requirements": [
            {"id": r.id, "project_id": r.project_id, "section_key": r.section_key, "requirement_text": r.requirement_text, "priority": r.priority, "status": r.status}
            for r in db.query(RequirementItem).filter(RequirementItem.project_id.in_(audit_project_ids)).all()
        ] if audit_project_ids else [],
        "evidence": [
            {"id": e.id, "project_id": e.project_id, "quote_text": e.quote_text, "confidence": e.confidence}
            for e in db.query(Evidence).filter(Evidence.project_id.in_(audit_project_ids)).all()
        ] if audit_project_ids else [],
        "execution_runs": [
            {"id": r.id, "project_id": r.project_id, "run_type": r.run_type, "status": r.status}
            for r in db.query(ExecutionRun).filter(ExecutionRun.project_id.in_(audit_project_ids)).all()
        ] if audit_project_ids else [],
        "review_comments": [
            {"id": c.id, "body": c.body, "author_type": c.author_type, "author_id": c.author_id, "created_at": str(c.created_at) if c.created_at else None}
            for c in db.query(ReviewComment).filter(ReviewComment.author_id == user.id).all()
        ],
        "section_versions": [
            {"id": v.id, "deliverable_section_id": v.deliverable_section_id, "version_number": v.version_number, "created_by_actor": v.created_by_actor}
            for v in db.query(SectionVersion).join(DeliverableSection).join(Deliverable).filter(Deliverable.project_id.in_(audit_project_ids)).all()
        ] if audit_project_ids else [],
        "audit_events": [
            {"id": e.id, "event_type": e.event_type, "actor_id": e.actor_id, "project_id": e.project_id, "timestamp": str(e.created_at)}
            for e in db.query(AuditEvent).filter(AuditEvent.actor_id == user.id).all()
        ],
    }
    return {"data": data}
