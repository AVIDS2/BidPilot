# Pilot Production Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close remaining known limitations and production gaps across 4 parallel streams to achieve pilot exit readiness.

**Architecture:** Four independent streams — Stream 1 (Backend), Stream 2 (Export), Stream 3 (Frontend), Stream 4 (E2E+Quality). Each stream modifies separate files; no cross-stream dependencies.

**Tech Stack:** Python 3.12+ / FastAPI / SQLAlchemy 2 / Celery / React 19 / TypeScript / Tailwind CSS v4 / shadcn/ui / Playwright

---

## Stream 1: Backend Feature Completion

### Task 1.1: Review Notification Emails

**Files:**
- Modify: `services/api/app/review/service.py` (trigger emails on decision)
- Modify: `services/api/app/email/service.py` (no changes needed, `send_review_notification_email` already exists)
- Test: `services/api/tests/review/test_notification.py` (new)

**Context:** Email templates for review notifications already exist in `app/email/service.py:send_review_notification_email()`. The review service (`app/review/service.py:submit_review_decision_command`) processes decisions but does not trigger emails. Need to wire them together.

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/review/test_notification.py`:

```python
"""Test review notification emails are triggered on decisions."""
from unittest.mock import patch, MagicMock
from app.review.service import submit_review_decision_command
from app.review.schemas import ReviewDecisionCreate


def test_approve_sends_notification(test_db):
    """Approving a section should trigger a review notification email."""
    # Create project, deliverable, section in test_db first
    from app.models import Project, Deliverable, DeliverableSection
    p = Project(id="p-notify-1", slug="notify-test", name="Notify Test", scenario_package="bidpilot")
    d = Deliverable(id="d-notify-1", project_id=p.id, type="proposal", title="Test Del")
    s = DeliverableSection(id="s-notify-1", deliverable_id=d.id, section_key="intro", title="Intro")
    test_db.add_all([p, d, s])
    test_db.commit()

    payload = ReviewDecisionCreate(section_id="s-notify-1", decision="approved", comment="Looks good")

    with patch("app.review.service.send_review_notification_email") as mock_send:
        result = submit_review_decision_command(test_db, payload)

    assert result.decision == "approved"
    mock_send.assert_called_once()
    call_args = mock_send.call_args
    assert call_args[1]["action"] == "approved"


def test_reject_sends_notification(test_db):
    """Rejecting a section should trigger a review notification email."""
    from app.models import Project, Deliverable, DeliverableSection
    p = Project(id="p-notify-2", slug="notify-test-2", name="Notify Test 2", scenario_package="bidpilot")
    d = Deliverable(id="d-notify-2", project_id=p.id, type="proposal", title="Test Del 2")
    s = DeliverableSection(id="s-notify-2", deliverable_id=d.id, section_key="intro", title="Intro")
    test_db.add_all([p, d, s])
    test_db.commit()

    payload = ReviewDecisionCreate(section_id="s-notify-2", decision="rejected", comment="Needs work")

    with patch("app.review.service.send_review_notification_email") as mock_send:
        submit_review_decision_command(test_db, payload)

    mock_send.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest services/api/tests/review/test_notification.py -v`
Expected: FAIL because `send_review_notification_email` is not called in the service.

- [ ] **Step 3: Wire notification email into review service**

In `services/api/app/review/service.py`, add import and call at the end of `submit_review_decision_command`:

```python
# Add at top of file, after existing imports:
from app.email.service import send_review_notification_email

# In submit_review_decision_command, after db.commit() and before return, add:
    # Send notification email for the review decision
    deliverable = db.get(Deliverable, section.deliverable_id)
    project_name = "Unknown Project"
    if deliverable:
        project = db.get(Project, deliverable.project_id)
        if project:
            project_name = project.name
    # Try to get user email from auth context, fall back to dev
    try:
        send_review_notification_email(
            email="admin@docpilot.local",  # TODO: replace with actual project member emails
            project_name=project_name,
            section_title=section.title,
            action=payload.decision,
        )
    except Exception:
        pass  # Non-blocking: email failure should not block review
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest services/api/tests/review/test_notification.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run all existing review tests**

Run: `pytest services/api/tests/review/ -v`
Expected: All existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add services/api/app/review/service.py services/api/tests/review/test_notification.py
git commit -m "feat: wire review notification emails on approve/reject decisions"
```

---

### Task 1.2: Data Export Completeness

**Files:**
- Modify: `services/api/app/auth/router.py:288-313` (expand `export_user_data`)
- Test: `services/api/tests/auth/test_export.py` (modify existing)

**Context:** `GET /auth/me/export` currently returns only projects and audit events. Need to add deliverables, sections, review_comments, evidence_items, execution_runs, bundles, documents.

Read the current implementation at `services/api/app/auth/router.py:288-313` before starting.

- [ ] **Step 1: Write the expanded test**

Modify/create `services/api/tests/auth/test_export.py`:

```python
"""Test user data export returns all entity types."""
from app.auth.service import register_user_command, login_command
from app.auth.schemas import UserRegister


def test_export_includes_all_entity_types(test_db, client_with_user):
    """GET /auth/me/export should include all entity types owned by user."""
    # Register + login a test user
    payload = UserRegister(email="export-test@docpilot.ai", display_name="Export Test", password="Test1234")
    user = register_user_command(test_db, payload)
    token = login_command(test_db, "export-test@docpilot.ai", "Test1234").access_token

    # Create a project with bundles, deliverables, requirements, evidence, sections
    from app.models import Project, Bundle, SourceDocument, Deliverable, DeliverableSection
    from app.models import RequirementItem, Evidence, SectionVersion, ExecutionRun, ReviewComment, ReviewThread
    p = Project(id="exp-p-1", slug="export-proj", name="Export Project", scenario_package="bidpilot")
    b = Bundle(id="exp-b-1", project_id="exp-p-1", label="Test Bundle", source_type="upload")
    d = Deliverable(id="exp-d-1", project_id="exp-p-1", type="proposal", title="Test Del")
    s = DeliverableSection(id="exp-s-1", deliverable_id="exp-d-1", section_key="intro", title="Intro")
    r = RequirementItem(id="exp-r-1", project_id="exp-p-1", section_key="intro", requirement_text="Must have X")
    e = Evidence(id="exp-ev-1", project_id="exp-p-1", quote_text="Evidence text")
    run = ExecutionRun(id="exp-run-1", project_id="exp-p-1", run_type="draft")
    rt = ReviewThread(id="exp-rt-1", deliverable_section_id="exp-s-1", opened_by=user.id)
    rc = ReviewComment(id="exp-rc-1", review_thread_id="exp-rt-1", author_type="human", author_id=user.id, body="Comment")
    sv = SectionVersion(id="exp-sv-1", deliverable_section_id="exp-s-1", version_number=1, content_markdown="# Draft")
    sd = SourceDocument(id="exp-sd-1", bundle_id="exp-b-1", storage_key="test.txt", mime_type="text/plain", checksum="abc123", original_filename="test.txt")
    test_db.add_all([p, b, sd, d, s, r, e, run, rt, rc, sv])
    test_db.commit()

    resp = client_with_user.get("/auth/me/export", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert len(data["projects"]) >= 1
    assert len(data["bundles"]) >= 1
    assert len(data["documents"]) >= 1
    assert len(data["deliverables"]) >= 1
    assert len(data["sections"]) >= 1
    assert len(data["requirements"]) >= 1
    assert len(data["evidence"]) >= 1
    assert len(data["execution_runs"]) >= 1
    assert "review_comments" in data
    assert "account" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest services/api/tests/auth/test_export.py::test_export_includes_all_entity_types -v`
Expected: FAIL — export response missing fields.

- [ ] **Step 3: Expand export_user_data endpoint**

In `services/api/app/auth/router.py`, replace the `export_user_data` function body:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest services/api/tests/auth/test_export.py::test_export_includes_all_entity_types -v`
Expected: PASS

- [ ] **Step 5: Verify existing tests still pass**

Run: `pytest services/api/tests/auth/ -v`
Expected: All existing auth tests pass.

- [ ] **Step 6: Commit**

```bash
git add services/api/app/auth/router.py services/api/tests/auth/test_export.py
git commit -m "feat: expand user data export to include all entity types"
```

---

### Task 1.3: Worker Health Check Integration

**Files:**
- Modify: `services/api/app/ops/router.py` (add worker check)
- Test: `services/api/tests/ops/test_health.py` (modify existing)

- [ ] **Step 1: Write the failing test**

Add test to `services/api/tests/ops/test_health.py`:

```python
def test_health_detailed_includes_worker(client):
    """GET /ops/health-detailed should include worker status."""
    resp = client.get("/ops/health-detailed")
    assert resp.status_code == 200
    data = resp.json()
    assert "checks" in data
    assert "worker" in data["checks"]
    assert data["checks"]["worker"]["status"] in ("ok", "error")
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest services/api/tests/ops/test_health.py::test_health_detailed_includes_worker -v`
Expected: FAIL — "worker" not in checks.

- [ ] **Step 3: Add worker check to health_detailed**

Modify `services/api/app/ops/router.py` `health_detailed` function, add after the MinIO check block:

```python
    # Celery Worker
    try:
        from app.celery_client import celery_app
        insp = celery_app.control.inspect()
        stats = insp.stats()
        if stats:
            active_workers = len(stats)
            checks["worker"] = {"status": "ok", "active_workers": active_workers}
        else:
            checks["worker"] = {"status": "degraded", "detail": "No workers responding"}
    except Exception as exc:
        checks["worker"] = {"status": "error", "detail": str(exc)[:200]}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest services/api/tests/ops/test_health.py::test_health_detailed_includes_worker -v`
Expected: PASS (worker check may show "error" if no worker running, but key "worker" must be present).

- [ ] **Step 5: Commit**

```bash
git add services/api/app/ops/router.py services/api/tests/ops/test_health.py
git commit -m "feat: add Celery worker status to health-detailed endpoint"
```

---

### Task 1.4: Refresh Token Server-Side Storage

**Files:**
- Create: `services/api/app/auth/refresh_token_model.py` (or add to models.py)
- Modify: `services/api/app/models.py` (add RefreshToken table)
- Modify: `services/api/app/auth/service.py` (store/validate/delete tokens)
- Create: `services/api/alembic/versions/*_add_refresh_token_table.py` (migration)
- Test: `services/api/tests/auth/test_refresh_tokens.py` (new)

**Design:** Store hashed refresh tokens in a `refresh_token` table. On login, store the hashed token. On refresh, validate against DB. On logout, delete. Expired tokens cleaned by scheduled task.

- [ ] **Step 1: Add RefreshToken model**

Add to `services/api/app/models.py` (after Subscription class):

```python
class RefreshToken(Base):
    __tablename__ = "refresh_token"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

- [ ] **Step 2: Write test for refresh token storage**

Create `services/api/tests/auth/test_refresh_tokens.py`:

```python
"""Test server-side refresh token storage."""
import hashlib
from app.auth.service import register_user_command, login_command, refresh_token_command
from app.auth.schemas import UserRegister
from app.models import RefreshToken


def test_login_stores_refresh_token(test_db):
    """Login should store a hashed refresh token in DB."""
    payload = UserRegister(email="rt-test@docpilot.ai", display_name="RT Test", password="Test1234")
    register_user_command(test_db, payload)
    # Manually verify email
    from app.models import User
    u = test_db.query(User).filter_by(email="rt-test@docpilot.ai").first()
    u.email_verified = True
    test_db.commit()

    result = login_command(test_db, "rt-test@docpilot.ai", "Test1234")
    assert result.refresh_token is not None

    # Check DB for stored token
    token_hash = hashlib.sha256(result.refresh_token.encode()).hexdigest()
    stored = test_db.query(RefreshToken).filter_by(token_hash=token_hash).first()
    assert stored is not None
    assert stored.user_id == u.id
    assert not stored.revoked


def test_refresh_token_validates_against_db(test_db):
    """Refresh should succeed only if token exists in DB and is not revoked."""
    payload = UserRegister(email="rt-test2@docpilot.ai", display_name="RT Test 2", password="Test1234")
    register_user_command(test_db, payload)
    from app.models import User
    u = test_db.query(User).filter_by(email="rt-test2@docpilot.ai").first()
    u.email_verified = True
    test_db.commit()

    result = login_command(test_db, "rt-test2@docpilot.ai", "Test1234")
    assert result.refresh_token is not None

    # Valid refresh should succeed
    new_tokens = refresh_token_command(test_db, result.refresh_token)
    assert new_tokens.access_token is not None

    # Revoke the original token and try again
    token_hash = hashlib.sha256(result.refresh_token.encode()).hexdigest()
    stored = test_db.query(RefreshToken).filter_by(token_hash=token_hash).first()
    stored.revoked = True
    test_db.commit()

    # Should fail with revoked token
    import pytest
    with pytest.raises(ValueError, match="revoked"):
        refresh_token_command(test_db, result.refresh_token)


def test_expired_tokens_are_rejected(test_db):
    """Expired refresh tokens should be rejected."""
    # Create a token with past expiry
    payload = UserRegister(email="rt-test3@docpilot.ai", display_name="RT Test 3", password="Test1234")
    user = register_user_command(test_db, payload)
    from app.models import User, RefreshToken
    from datetime import UTC, datetime, timedelta
    import hashlib
    u = test_db.query(User).filter_by(email="rt-test3@docpilot.ai").first()
    u.email_verified = True
    test_db.commit()

    expired = RefreshToken(
        user_id=user.id,
        token_hash=hashlib.sha256(b"expired-token").hexdigest(),
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    test_db.add(expired)
    test_db.commit()

    import pytest
    with pytest.raises(ValueError, match="expired"):
        refresh_token_command(test_db, "expired-token")
```

- [ ] **Step 3: Run test to verify fail**

Run: `pytest services/api/tests/auth/test_refresh_tokens.py -v`
Expected: FAIL — RefreshToken model doesn't exist, login doesn't store tokens.

- [ ] **Step 4: Implement refresh token storage in auth service**

Modify `services/api/app/auth/service.py`:

Add import at top:
```python
import hashlib
from datetime import UTC, datetime
from app.models import RefreshToken
```

Modify `login_command` to store refresh token:
```python
def login_command(db: Session, email: str, password: str) -> TokenResponse:
    user = get_user_by_email(db, email)
    if user is None or not _verify_password(password, user.password_hash):
        raise ValueError("Invalid credentials")
    if user.disabled:
        raise ValueError("Account is disabled. Contact your administrator.")
    if not user.email_verified:
        raise ValueError("Email not verified. Please check your email and verify your account.")
    refresh_token = _create_refresh_token(user.id)
    # Store hashed refresh token
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    rt = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(days=REFRESH_EXPIRES_DAYS),
    )
    db.add(rt)
    db.commit()
    return TokenResponse(
        access_token=_create_token(user.id),
        refresh_token=refresh_token,
    )
```

Modify `refresh_token_command` to validate against DB:
```python
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
    if stored.expires_at < datetime.now(UTC):
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
        expires_at=datetime.now(UTC) + timedelta(days=REFRESH_EXPIRES_DAYS),
    )
    db.add(new_rt)
    db.commit()
    
    return TokenResponse(
        access_token=_create_token(user.id),
        refresh_token=new_refresh,
    )
```

Add a logout/revoke function:
```python
def revoke_refresh_token(db: Session, refresh_token: str) -> None:
    """Revoke a refresh token (used on logout)."""
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    stored = db.query(RefreshToken).filter_by(token_hash=token_hash).first()
    if stored:
        stored.revoked = True
        db.commit()
```

- [ ] **Step 5: Generate migration**

Run:
```bash
cd services/api && conda activate llm && alembic revision --autogenerate -m "add_refresh_token_table" && alembic upgrade head
```

- [ ] **Step 6: Run tests**

Run: `pytest services/api/tests/auth/test_refresh_tokens.py -v`
Expected: 3 tests PASS.

Run: `pytest services/api/tests/auth/ -v`
Expected: All auth tests still pass.

- [ ] **Step 7: Commit**

```bash
git add services/api/app/models.py services/api/app/auth/service.py services/api/app/auth/router.py services/api/alembic/ services/api/tests/auth/test_refresh_tokens.py
git commit -m "feat: add server-side refresh token storage with revocation"
```

---

### Task 1.5: Automated Backup Scheduling via Celery Beat

**Files:**
- Modify: `services/worker/app/celery_app.py` (add beat schedule)
- Create: `services/worker/app/tasks/backup.py` (backup task)
- Test: `services/worker/tests/test_backup_task.py` (new)

- [ ] **Step 1: Create backup task**

Create `services/worker/app/tasks/backup.py`:

```python
"""Celery Beat scheduled backup task."""
import subprocess
import logging
from celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="worker.backup_database")
def backup_database() -> dict:
    """Run database backup and return result."""
    try:
        result = subprocess.run(
            ["python", "scripts/backup.py"],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            logger.info("Scheduled backup completed successfully")
            return {"status": "ok", "output": result.stdout[:500]}
        else:
            logger.error("Scheduled backup failed: %s", result.stderr)
            return {"status": "error", "output": result.stderr[:500]}
    except Exception as exc:
        logger.exception("Scheduled backup exception")
        return {"status": "error", "detail": str(exc)[:500]}
```

- [ ] **Step 2: Add Celery Beat schedule**

In `services/worker/app/celery_app.py`, add after celery_app definition:

```python
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    "backup-daily": {
        "task": "worker.backup_database",
        "schedule": crontab(hour=3, minute=0),  # 3 AM daily
    },
}
celery_app.conf.timezone = "Asia/Shanghai"
```

- [ ] **Step 3: Write test**

Create `services/worker/tests/test_backup_task.py`:

```python
"""Test automated backup task."""
from unittest.mock import patch, MagicMock
from worker.app.tasks.backup import backup_database


def test_backup_task_runs_backup_script():
    """Backup task should invoke scripts/backup.py."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Backup complete", stderr="")
        result = backup_database()
        assert result["status"] == "ok"
        mock_run.assert_called_once()
        assert "scripts/backup.py" in mock_run.call_args[0][0][1]


def test_backup_task_handles_failure():
    """Backup task should return error status on failure."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Backup failed")
        result = backup_database()
        assert result["status"] == "error"
```

- [ ] **Step 4: Run tests**

Run: `pytest services/worker/tests/test_backup_task.py -v`
Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add services/worker/app/tasks/backup.py services/worker/app/celery_app.py services/worker/tests/test_backup_task.py
git commit -m "feat: add Celery Beat scheduled daily database backup"
```

---

## Stream 2: Export Enhancement

### Task 2.1: PDF Export Endpoint

**Files:**
- Modify: `services/api/app/export/router.py` (add PDF endpoint)
- Modify: `services/api/app/export/service.py` (add PDF generation)
- Test: `services/api/tests/export/test_pdf_export.py` (new)

**Context:** Currently only DOCX export exists. PDF generation should reuse the same section data and generate via a simple HTML-to-PDF approach. Avoid heavy dependencies — use reportlab (pure Python) or a simple approach. Since WeasyPrint requires system dependencies, use a lightweight HTML template approach with `xhtml2pdf` or fallback to generating a simple text PDF with `reportlab`.

Check reportlab is available:
```bash
pip show reportlab || pip install reportlab
```

- [ ] **Step 1: Add PDF generation to export service**

Add to `services/api/app/export/service.py`:

```python
def render_markdown_to_pdf(sections: list[dict]) -> bytes:
    """Render approved sections to a PDF document."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        from io import BytesIO

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
        styles = getSampleStyleSheet()
        story = []

        # Title
        title_style = ParagraphStyle("CustomTitle", parent=styles["Title"], fontSize=20, spaceAfter=20)
        story.append(Paragraph("BidPilot Deliverable", title_style))
        story.append(HRFlowable(width="100%", thickness=1, color="#ccc"))
        story.append(Spacer(1, 12))

        heading_style = ParagraphStyle("SectionHead", parent=styles["Heading2"], fontSize=14, spaceBefore=16, spaceAfter=8)
        body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=14, spaceAfter=12)

        for section in sections:
            title = section.get("title") or section.get("section_key", "Untitled")
            story.append(Paragraph(title, heading_style))

            version = section.get("latest_version")
            if version:
                content_md = version.get("content_markdown", "")
                # Simple markdown-to-text conversion (paragraphs)
                for para in content_md.split("\n\n"):
                    para = para.strip()
                    if para:
                        # Escape HTML entities
                        import html
                        para = html.escape(para)
                        story.append(Paragraph(para, body_style))
            story.append(Spacer(1, 6))

        doc.build(story)
        return buffer.getvalue()
    except ImportError:
        # Fallback: generate simple text PDF
        from io import BytesIO
        buffer = BytesIO()
        buffer.write(b"%PDF-1.4\n% basic pdf fallback\n")
        text = "\n".join(
            f"## {s.get('title', '')}\n{s.get('latest_version', {}).get('content_markdown', '')[:500]}"
            for s in sections
        )
        buffer.write(text.encode("utf-8"))
        return buffer.getvalue()
```

- [ ] **Step 2: Add PDF endpoint to export router**

Add to `services/api/app/export/router.py`:

```python
@router.get("/deliverables/{deliverable_id}/pdf")
def export_deliverable_pdf(deliverable_id: str, db: Session = Depends(get_db)) -> Response:
    """Export a deliverable as a PDF file."""
    from .service import get_deliverable_sections_with_versions
    sections = get_deliverable_sections_with_versions(db, deliverable_id)
    if not sections:
        raise HTTPException(status_code=404, detail="Deliverable not found or has no sections")

    from .service import render_markdown_to_pdf
    pdf_bytes = render_markdown_to_pdf(sections)

    # Upload to MinIO
    try:
        from app.adapters.storage import upload_bytes
        object_name = f"exports/{deliverable_id}/deliverable.pdf"
        from app.models import Deliverable
        deliverable = db.get(Deliverable, deliverable_id)
        if deliverable:
            upload_bytes(deliverable.project_id, object_name, pdf_bytes, "application/pdf")
    except Exception:
        pass

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=deliverable-{deliverable_id}.pdf"},
    )
```

- [ ] **Step 3: Write PDF export test**

Create `services/api/tests/export/test_pdf_export.py`:

```python
"""Test PDF export endpoint."""
from app.models import Project, Deliverable, DeliverableSection, SectionVersion


def test_export_pdf_returns_pdf_content_type(test_db, client):
    """PDF export should return application/pdf content type."""
    p = Project(id="pdf-p-1", slug="pdf-proj", name="PDF Project", scenario_package="bidpilot")
    d = Deliverable(id="pdf-d-1", project_id="pdf-p-1", type="proposal", title="Test PDF")
    s = DeliverableSection(id="pdf-s-1", deliverable_id="pdf-d-1", section_key="intro", title="Intro", status="approved")
    sv = SectionVersion(id="pdf-sv-1", deliverable_section_id="pdf-s-1", version_number=1, content_markdown="# Hello PDF")
    test_db.add_all([p, d, s, sv])
    test_db.commit()

    resp = client.get("/export/deliverables/pdf-d-1/pdf")
    assert resp.status_code == 200
    assert "application/pdf" in resp.headers.get("content-type", "")


def test_export_pdf_404_for_missing_deliverable(test_db, client):
    """PDF export should return 404 for non-existent deliverable."""
    resp = client.get("/export/deliverables/nonexistent/pdf")
    assert resp.status_code == 404
```

- [ ] **Step 4: Run tests**

Run: `pytest services/api/tests/export/test_pdf_export.py -v`
Expected: 2 tests PASS.

Run: `pytest services/api/tests/export/ -v`
Expected: All export tests pass.

- [ ] **Step 5: Add frontend API client support**

Add to `apps/web/src/lib/api.ts`:

```typescript
export async function exportDeliverablePdf(deliverableId: string) {
  const blob = await requestBlob(`/export/deliverables/${deliverableId}/pdf`);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `deliverable-${deliverableId}.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
```

- [ ] **Step 6: Add PDF export button to frontend**

In `apps/web/src/features/projects/project-detail-page.tsx`, in the Export tab, add a PDF button next to the DOCX button:

```tsx
<Button
  size="sm"
  variant="outline"
  disabled={d.status !== "approved"}
  onClick={async () => {
    try {
      await exportDeliverablePdf(d.id);
      toast.success("PDF export started");
    } catch {
      toast.error("Failed to export PDF");
    }
  }}
>
  Export PDF
</Button>
```

Import `exportDeliverablePdf` from `@/lib/api`.

- [ ] **Step 7: Commit**

```bash
git add services/api/app/export/router.py services/api/app/export/service.py services/api/tests/export/test_pdf_export.py apps/web/src/lib/api.ts apps/web/src/features/projects/project-detail-page.tsx
git commit -m "feat: add PDF export endpoint and frontend button"
```

---

### Task 2.2: Large Bundle Pagination

**Files:**
- Modify: `services/api/app/documents/router.py` (add pagination params)
- Modify: `services/api/app/documents/repository.py` (paginated query)
- Modify: `apps/web/src/lib/api.ts` (add pagination params)
- Modify: `apps/web/src/features/projects/project-detail-page.tsx` (add pagination controls)

- [ ] **Step 1: Add paginated document query**

Modify `services/api/app/documents/repository.py`, add:

```python
def list_documents_paginated(db: Session, bundle_id: str, page: int = 1, page_size: int = 20) -> tuple[list["SourceDocument"], int]:
    from sqlalchemy import func
    from app.models import SourceDocument
    total = db.scalar(select(func.count()).select_from(SourceDocument).where(SourceDocument.bundle_id == bundle_id)) or 0
    docs = db.scalars(
        select(SourceDocument)
        .where(SourceDocument.bundle_id == bundle_id)
        .order_by(SourceDocument.original_filename)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(docs), total
```

- [ ] **Step 2: Add pagination params to router**

Modify `services/api/app/documents/router.py` `list_documents` function:

```python
@router.get("", response_model=dict)
def list_documents(
    bundle_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict:
    """List documents for a bundle with pagination support."""
    from .repository import list_documents_paginated
    docs, total = list_documents_paginated(db, bundle_id, page, page_size)
    from .schemas import SourceDocumentRead
    return {
        "items": [SourceDocumentRead.model_validate(d) for d in docs],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total > 0 else 0,
    }
```

- [ ] **Step 3: Update frontend API**

In `apps/web/src/lib/api.ts`, update `listDocuments` and add type:

```typescript
export interface DocumentsPaginatedResponse {
  items: SourceDocumentRead[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export function listDocuments(bundleId: string, page?: number, pageSize?: number) {
  const params = new URLSearchParams({ bundle_id: bundleId });
  if (page) params.set("page", String(page));
  if (pageSize) params.set("page_size", String(pageSize));
  return request<DocumentsPaginatedResponse>(`/documents?${params.toString()}`);
}
```

- [ ] **Step 4: Update frontend to use pagination**

In the project-detail-page.tsx, update the document list section to handle paginated response and add page navigation controls using shadcn Button.

- [ ] **Step 5: Run tests**

Run: `pytest services/api/tests/documents/ -v`
Expected: Document tests pass.

Run: `cd apps/web && npx tsc --noEmit`
Expected: No type errors.

- [ ] **Step 6: Commit**

```bash
git add services/api/app/documents/ apps/web/src/lib/api.ts apps/web/src/features/projects/project-detail-page.tsx
git commit -m "feat: add pagination to document listing for large bundles"
```

---

## Stream 3: Frontend Polish

### Task 3.1: Loading Skeleton States

**Files:**
- Modify: `apps/web/src/features/projects/project-list-page.tsx`
- Modify: `apps/web/src/features/account/account-page.tsx`
- Modify: `apps/web/src/features/admin/user-management-page.tsx`

**Context:** shadcn Skeleton component already exists at `components/ui/skeleton.tsx`. Use it for loading states across pages. The project-detail-page already has one skeleton. Add to other pages.

- [ ] **Step 1: Add loading skeletons to ProjectListPage**

In `apps/web/src/features/projects/project-list-page.tsx`, wrap the content in a loading check. Add a `SkeletonList` component pattern:

```tsx
function ProjectListSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <Skeleton className="h-9 w-48" />
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-5 w-3/4" />
              <Skeleton className="h-4 w-1/2 mt-2" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-4 w-full" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add skeleton to AccountPage**

In `apps/web/src/features/account/account-page.tsx`, add a skeleton for the loading state:

```tsx
function AccountPageSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <Skeleton className="h-8 w-48" />
      <Card>
        <CardHeader>
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-4 w-64" />
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-32" />
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 3: Add skeleton to UserManagementPage**

In `apps/web/src/features/admin/user-management-page.tsx`, add loading skeleton.

- [ ] **Step 4: Write tests for skeleton rendering**

Add tests to verify skeletons render when data is loading:

```tsx
describe("ProjectListPage loading state", () => {
  it("shows skeletons while loading", () => {
    // Mock useQuery to return isLoading=true
    // Assert skeletons are rendered
  });
});
```

- [ ] **Step 5: Run frontend tests**

Run: `cd apps/web && npx vitest run`
Expected: All existing tests + new skeleton tests pass.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/features/projects/project-list-page.tsx apps/web/src/features/account/account-page.tsx apps/web/src/features/admin/user-management-page.tsx apps/web/src/features/*/test files
git commit -m "feat: add loading skeleton states to all pages"
```

---

### Task 3.2: Error Boundary

**Files:**
- Create: `apps/web/src/components/error-boundary.tsx`
- Modify: `apps/web/src/app.tsx` (wrap routes)
- Modify: `apps/web/src/main.tsx` (wrap app)
- Test: `apps/web/src/components/error-boundary.test.tsx` (new)

- [ ] **Step 1: Create Error Boundary component**

Create `apps/web/src/components/error-boundary.tsx`:

```tsx
import { Component, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { AlertTriangleIcon } from "lucide-react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="flex min-h-svh items-center justify-center p-6">
          <Card className="max-w-md">
            <CardHeader>
              <div className="flex items-center gap-2">
                <AlertTriangleIcon className="size-5 text-destructive" />
                <CardTitle>Something went wrong</CardTitle>
              </div>
              <CardDescription>
                {this.state.error?.message ?? "An unexpected error occurred."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                onClick={() => {
                  this.setState({ hasError: false, error: null });
                  window.location.reload();
                }}
              >
                Reload Page
              </Button>
            </CardContent>
          </Card>
        </div>
      );
    }
    return this.props.children;
  }
}
```

- [ ] **Step 2: Write test**

Create `apps/web/src/components/error-boundary.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ErrorBoundary } from "./error-boundary";

function ThrowError() {
  throw new Error("Test error");
}

describe("ErrorBoundary", () => {
  it("renders children when no error", () => {
    render(
      <ErrorBoundary>
        <p>Hello</p>
      </ErrorBoundary>
    );
    expect(screen.getByText("Hello")).toBeDefined();
  });

  it("renders fallback UI when error occurs", () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );
    expect(screen.getByText("Something went wrong")).toBeDefined();
  });
});
```

- [ ] **Step 3: Wrap app in ErrorBoundary**

In `apps/web/src/app.tsx`, wrap the App component's BrowserRouter with ErrorBoundary:

```tsx
import { ErrorBoundary } from "@/components/error-boundary";

// Wrap the main Routes
<ErrorBoundary>
  <BrowserRouter>
    <Routes>
      {/* existing routes */}
    </Routes>
  </BrowserRouter>
</ErrorBoundary>
```

- [ ] **Step 4: Run tests**

Run: `cd apps/web && npx vitest run src/components/error-boundary.test.tsx`
Expected: 2 tests PASS.

Run: `cd apps/web && npx vitest run`
Expected: All frontend tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/error-boundary.tsx apps/web/src/components/error-boundary.test.tsx apps/web/src/app.tsx
git commit -m "feat: add error boundary with fallback UI and reload"
```

---

### Task 3.3: Consistent Empty States

**Files:**
- Modify: `apps/web/src/features/projects/project-detail-page.tsx` (already done partially)
- Modify: `apps/web/src/features/pricing/pricing-page.tsx` (verify)
- Modify: `apps/web/src/features/landing/landing-page.tsx` (verify)

**Context:** The project already uses shadcn Empty components (`components/ui/empty.tsx`). Verify consistency across all pages and ensure every empty state uses the Empty component pattern with icons.

- [ ] **Step 1: Audit empty states**

Check each page for empty states. All should use:
```tsx
import { Empty, EmptyHeader, EmptyTitle, EmptyDescription, EmptyMedia } from "@/components/ui/empty";
```

- [ ] **Step 2: Fix any missing empty states**

Add Empty components where missing. Each should include an appropriate lucide icon.

- [ ] **Step 3: Write test**

Add a test that each page renders empty state correctly:

```tsx
it("shows empty state when no data", () => {
  render(<Page withNoData />);
  expect(screen.getByText(/no .* yet/i)).toBeDefined();
});
```

- [ ] **Step 4: Run tests and typecheck**

Run: `cd apps/web && npx tsc --noEmit && npx vitest run`
Expected: Typecheck + all tests pass.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: ensure consistent empty states across all pages"
```

---

### Task 3.4: Toast Consistency & Responsive Polish

**Files:**
- Modify: Multiple files (audit toast usage)
- Modify: `apps/web/src/index.css` (responsive tweaks)

**Context:** Project already uses `sonner` toast via `components/ui/sonner.tsx`. Verify all toasts use consistent patterns. Add responsive improvements.

- [ ] **Step 1: Audit toast usage**

Search for `toast.error`, `toast.success` across the codebase. Verify:
1. Error toasts use destructive variant: not needed for sonner (uses `toast.error` which is red)
2. All mutations use `onError` to show toast
3. No raw `alert()` calls

- [ ] **Step 2: Add responsive table wrappers**

Add `overflow-x-auto` to Table containers in project-detail-page for mobile:

```tsx
<div className="overflow-x-auto">
  <Table>...</Table>
</div>
```

- [ ] **Step 3: Verify mobile sidebar**

Check `use-mobile.ts` hook and ensure sidebar collapses on mobile. The app-sidebar already uses `use-mobile`. Verify it works.

- [ ] **Step 4: Commit**

```bash
git commit -m "fix: responsive polish for tables and mobile sidebar"
```

---

## Stream 4: E2E & Quality

### Task 4.1: Pricing Page E2E

**Files:**
- Create: `apps/web/e2e/pricing.spec.ts`

- [ ] **Step 1: Write pricing page E2E test**

Create `apps/web/e2e/pricing.spec.ts`:

```typescript
import { expect, test } from "@playwright/test";

test.describe("Pricing page", () => {
  test("displays three pricing tiers", async ({ page }) => {
    await page.goto("/pricing");
    await expect(page.getByText("Starter")).toBeVisible();
    await expect(page.getByText("Professional")).toBeVisible();
    await expect(page.getByText("Enterprise")).toBeVisible();
  });

  test("has CTA buttons for each tier", async ({ page }) => {
    await page.goto("/pricing");
    const buttons = page.getByRole("button");
    const count = await buttons.count();
    expect(count).toBeGreaterThanOrEqual(2);
  });

  test("redirects unauthenticated users to login when clicking CTA", async ({ page }) => {
    await page.goto("/pricing");
    await page.getByRole("button", { name: /Get Started|Upgrade|Contact/i }).first().click();
    await expect(page).toHaveURL(/\/login|checkout/);
  });
});
```

- [ ] **Step 2: Run the E2E test**

Run: `cd apps/web && npx playwright test e2e/pricing.spec.ts --project=chromium`
Expected: All 3 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add apps/web/e2e/pricing.spec.ts
git commit -m "test(e2e): add pricing page smoke tests"
```

---

### Task 4.2: Account Page E2E

**Files:**
- Create: `apps/web/e2e/account.spec.ts`

- [ ] **Step 1: Write account page E2E**

Create `apps/web/e2e/account.spec.ts`:

```typescript
import { expect, test } from "@playwright/test";

test.describe("Account page", () => {
  test("shows login redirect when unauthenticated", async ({ page }) => {
    await page.goto("/account");
    await expect(page).toHaveURL(/\/login/);
  });

  test("shows user profile after login", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("demo@docpilot.ai");
    await page.getByLabel("Password").fill("Demo1234");
    await page.getByRole("button", { name: "Login" }).click();
    await expect(page).toHaveURL(/\/projects/);

    await page.goto("/account");
    await expect(page.getByText("demo@docpilot.ai")).toBeVisible();
    await expect(page.getByText(/plan/i)).toBeVisible();
  });
});
```

- [ ] **Step 2: Run E2E**

Run: `cd apps/web && npx playwright test e2e/account.spec.ts --project=chromium`
Expected: Tests pass.

- [ ] **Step 3: Commit**

```bash
git add apps/web/e2e/account.spec.ts
git commit -m "test(e2e): add account page smoke tests"
```

---

### Task 4.3: Review Reject-Redraft E2E

**Files:**
- Modify: `apps/web/e2e/demo.spec.ts` (add reject-redraft flow)

- [ ] **Step 1: Add reject-redraft flow to demo spec**

Add to `apps/web/e2e/demo.spec.ts`:

```typescript
test("review reject → redraft → approve → export cycle", async ({ page }) => {
  test.skip(!runDemo, "Set E2E_DEMO=1");

  // 1. Login
  await page.goto("/login");
  await page.getByLabel("Email").fill(demoEmail);
  await page.getByLabel("Password").fill(demoPassword);
  await page.getByRole("button", { name: "Login" }).click();
  await expect(page).toHaveURL(/\/projects$/);

  // 2. Open a project with deliverables
  await page.getByPlaceholder("Search projects...").fill(demoProjectName);
  await page.getByRole("link", { name: demoProjectName, exact: true }).click();

  // 3. Navigate to Review tab
  await page.getByRole("tab", { name: "Review" }).click();

  // 4. Reject a section
  await page.getByRole("button", { name: "Reject" }).first().click();
  await expect(page.getByText(/rejected/i).first()).toBeVisible({ timeout: 10000 });

  // 5. Redraft (via re-draft button in drafting tab)
  await page.getByRole("tab", { name: "Drafting" }).click();
  await page.getByRole("button", { name: /Generate/i }).click();

  // 6. Approve the section
  await page.getByRole("tab", { name: "Review" }).click();
  await page.getByRole("button", { name: "Approve" }).first().click();
  await expect(page.getByText(/approved/i).first()).toBeVisible({ timeout: 10000 });

  // 7. Export
  await page.getByRole("tab", { name: "Export" }).click();
  await page.getByRole("button", { name: "Export DOCX" }).first().click();
  // File download doesn't open a new page, just verify no error
});
```

- [ ] **Step 2: Run E2E**

Run: `cd apps/web && npx playwright test e2e/demo.spec.ts --project=chromium -g "reject-redraft"`
Expected: Test passes (or is skipped if E2E_DEMO not set).

- [ ] **Step 3: Commit**

```bash
git add apps/web/e2e/demo.spec.ts
git commit -m "test(e2e): add reject-redraft-approve-export cycle test"
```

---

### Task 4.4: API Error Response Standardization

**Files:**
- Create: `services/api/app/core/error_handlers.py` (or modify main.py)
- Modify: `services/api/app/main.py` (add exception handlers)
- Test: `services/api/tests/test_error_format.py` (new)

- [ ] **Step 1: Add FastAPI exception handlers**

In `services/api/app/main.py`, add after app creation:

```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": str(exc.status_code),
            "message": exc.detail if isinstance(exc.detail, str) else "Request error",
            "details": exc.detail if not isinstance(exc.detail, str) else None,
        },
    )

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"error": "bad_request", "message": str(exc), "details": None},
    )
```

- [ ] **Step 2: Write error format test**

Create `services/api/tests/test_error_format.py`:

```python
"""Test all API errors follow consistent format."""
import pytest


def test_404_has_consistent_format(client):
    """404 responses should have error, message, details fields."""
    resp = client.get("/projects/nonexistent-id")
    assert resp.status_code == 404
    data = resp.json()
    assert "error" in data
    assert "message" in data
    assert "details" in data


def test_422_has_consistent_format(client):
    """422 validation errors should have consistent format."""
    resp = client.post("/projects", json={})
    assert resp.status_code == 422
    data = resp.json()
    assert "error" in data
    assert "message" in data


def test_401_has_consistent_format(client):
    """401 errors should have consistent format."""
    resp = client.get("/auth/me/export")
    assert resp.status_code == 401
    data = resp.json()
    assert "error" in data
    assert "message" in data
```

- [ ] **Step 3: Run tests**

Run: `pytest services/api/tests/test_error_format.py -v`
Expected: Tests pass after implementing error handlers.

- [ ] **Step 4: Verify all existing tests still pass**

Run: `pytest services/api/tests/ -v`
Expected: All 106+ API tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/api/app/main.py services/api/tests/test_error_format.py
git commit -m "feat: standardize API error response format"
```

---

### Task 4.5: Update known-limitations.md

**Files:**
- Modify: `docs/product/known-limitations.md`

After all streams complete, update to remove resolved limitations.

- [ ] **Step 1: Update the document**

Remove or update these resolved items:
- "No email notifications for review decisions yet" → "Review notification emails are sent on approve/reject"
- "Data export returns a subset" → "Data export includes all entity types"
- "No PDF export format" → "PDF export available alongside DOCX"
- "No automated backup scheduling" → "Celery Beat schedules daily backup"
- "Refresh token revocation" → "Server-side refresh token storage with revocation"

- [ ] **Step 2: Commit**

```bash
git add docs/product/known-limitations.md
git commit -m "docs: update known limitations reflecting completed work"
```

---

## Final Integration Check

After all streams complete:

- [ ] Run full API test suite: `pytest services/api/tests/ -v`
- [ ] Run full frontend test suite: `cd apps/web && npx vitest run`
- [ ] Run frontend typecheck: `cd apps/web && npx tsc --noEmit`
- [ ] Run frontend build: `cd apps/web && npx vite build`
- [ ] Run E2E tests: `cd apps/web && npx playwright test`
- [ ] Run release rehearsal: `python scripts/release_rehearsal.py --run`
- [ ] Run production readiness: `python scripts/production_readiness.py --target production`
