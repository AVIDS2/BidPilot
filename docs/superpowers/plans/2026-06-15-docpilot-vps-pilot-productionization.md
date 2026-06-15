# DocPilot VPS Pilot Productionization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make DocPilot safe to deploy on the VPS for a controlled HTTPS pilot with authentication, production URLs, SMTP links, AI workflow trial quota, and repeatable deployment checks.

**Architecture:** Keep the current single-node architecture and harden it instead of redesigning the platform. Add small configuration helpers, server-side quota enforcement, focused access-control checks, and deployment docs/scripts around the existing FastAPI, Celery, Vite, PostgreSQL, Redis, and MinIO stack.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, Celery, Redis, PostgreSQL/pgvector, MinIO, React/Vite, Vitest, pytest, PowerShell on Windows.

---

## Scope Guard

Implement only the controlled VPS pilot scope from `docs/superpowers/specs/2026-06-15-docpilot-vps-pilot-productionization-design.md`.

Do not implement in this plan:

- full Stripe production billing portal;
- enterprise SSO/MFA;
- Kubernetes;
- new scenario packages;
- large UI redesigns;
- public SLA or complete commercial support tooling.

## Key Existing Files

- `services/api/app/main.py` — FastAPI app, CORS, router registration.
- `services/api/app/email/service.py` — SMTP/console email adapter and link generation.
- `services/api/app/billing/router.py` — Stripe checkout/webhook routes.
- `scripts/production_readiness.py` — production environment gate.
- `services/api/app/models.py` — SQLAlchemy domain models.
- `services/api/alembic/versions/` — database migrations.
- `services/api/app/drafting/service.py` — draft/redraft run creation and Celery enqueue.
- `services/api/app/drafting/router.py` — drafting API routes.
- `services/api/app/assistant/tools.py` — assistant tool wrappers around platform services.
- `services/api/app/projects/router.py` — project endpoints; currently some routes need explicit org checks.
- `services/api/app/projects/service.py` and `services/api/app/projects/repository.py` — project persistence helpers.
- `services/api/.env.example` — API env sample.
- `compose.yml` — currently infrastructure only: PostgreSQL, Redis, MinIO.
- `docs/ops/deployment-and-runbook.md` — general deployment/runbook.
- `docs/ops/release-checklist.md` — release gate.
- `docs/product/known-limitations.md` — pre-pilot limitations.

## Suggested Execution Order

1. Production URL and readiness checks.
2. Email and billing URL tests.
3. Auth/project access hardening.
4. Usage ledger and workflow quota.
5. Frontend quota error polish.
6. Deployment packaging/runbook.
7. Final verification suite.

---

### Task 1: Add Central Runtime Settings

**Files:**

- Create: `services/api/app/core/__init__.py`
- Create: `services/api/app/core/settings.py`
- Modify: `services/api/app/main.py`
- Test: `services/api/tests/test_runtime_settings.py`

- [ ] **Step 1: Write failing settings tests**

Create `services/api/tests/test_runtime_settings.py`:

```python
import importlib


def test_app_url_trims_trailing_slash(monkeypatch):
    monkeypatch.setenv("DOCPILOT_APP_URL", "https://bidpilot.rglens.com/")
    from app.core import settings

    importlib.reload(settings)

    assert settings.get_app_url() == "https://bidpilot.rglens.com"


def test_cors_origins_include_local_defaults(monkeypatch):
    monkeypatch.delenv("DOCPILOT_CORS_ORIGINS", raising=False)
    from app.core import settings

    importlib.reload(settings)

    assert "http://localhost:5173" in settings.get_cors_origins()
    assert "http://127.0.0.1:5173" in settings.get_cors_origins()


def test_cors_origins_parse_comma_list(monkeypatch):
    monkeypatch.setenv(
        "DOCPILOT_CORS_ORIGINS",
        "https://bidpilot.rglens.com, https://api.bidpilot.rglens.com/",
    )
    from app.core import settings

    importlib.reload(settings)

    assert settings.get_cors_origins() == [
        "https://bidpilot.rglens.com",
        "https://api.bidpilot.rglens.com",
    ]
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
uv run --directory services/api pytest tests/test_runtime_settings.py -q
```

Expected:

- fails because `app.core.settings` does not exist.

- [ ] **Step 3: Implement settings module**

Create `services/api/app/core/__init__.py`:

```python
"""Core runtime configuration helpers."""
```

Create `services/api/app/core/settings.py`:

```python
from __future__ import annotations

import os


LOCAL_APP_URL = "http://localhost:5173"
LOCAL_API_URL = "http://localhost:8000"
LOCAL_CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def _clean_origin(value: str) -> str:
    return value.strip().rstrip("/")


def get_app_url() -> str:
    return _clean_origin(os.environ.get("DOCPILOT_APP_URL", LOCAL_APP_URL))


def get_api_url() -> str:
    return _clean_origin(os.environ.get("DOCPILOT_API_URL", LOCAL_API_URL))


def get_cors_origins() -> list[str]:
    raw = os.environ.get("DOCPILOT_CORS_ORIGINS")
    if not raw:
        return LOCAL_CORS_ORIGINS.copy()
    origins = [_clean_origin(item) for item in raw.split(",")]
    return [origin for origin in origins if origin]
```

- [ ] **Step 4: Wire CORS through settings**

Modify `services/api/app/main.py`:

```python
from app.core.settings import get_cors_origins
```

Replace the hardcoded CORS origins:

```python
allow_origins=get_cors_origins(),
```

- [ ] **Step 5: Verify tests**

Run:

```powershell
uv run --directory services/api pytest tests/test_runtime_settings.py -q
```

Expected:

- all tests pass.

---

### Task 2: Replace Production-Facing Localhost Links

**Files:**

- Modify: `services/api/app/email/service.py`
- Modify: `services/api/app/billing/router.py`
- Test: `services/api/tests/test_url_configuration.py`
- Test: `services/api/tests/billing/test_billing.py`

- [ ] **Step 1: Write failing URL tests**

Create `services/api/tests/test_url_configuration.py`:

```python
import importlib
from unittest.mock import patch


def test_invitation_email_uses_configured_app_url(monkeypatch):
    monkeypatch.setenv("DOCPILOT_APP_URL", "https://bidpilot.rglens.com")
    from app.email import service

    importlib.reload(service)

    sent = []

    def capture(message):
        sent.append(message)

    with patch("app.email.service.send_email", side_effect=capture):
        service.send_invitation_email("user@example.com", "invite-token", "default")

    assert sent
    assert "https://bidpilot.rglens.com/register?invitation=invite-token" in sent[0].body_text
    assert "http://localhost:5173" not in sent[0].body_text


def test_verification_and_reset_urls_use_configured_app_url(monkeypatch):
    monkeypatch.setenv("DOCPILOT_APP_URL", "https://bidpilot.rglens.com")
    from app.email import service

    importlib.reload(service)

    sent = []

    def capture(message):
        sent.append(message)

    with patch("app.email.service.send_email", side_effect=capture):
        service.send_email_verification_email("user@example.com", "verify-token")
        service.send_password_reset_email("user@example.com", "reset-token")

    bodies = "\n".join(message.body_text for message in sent)
    assert "https://bidpilot.rglens.com/verify-email?token=verify-token" in bodies
    assert "https://bidpilot.rglens.com/reset-password?token=reset-token" in bodies
```

- [ ] **Step 2: Extend billing checkout test**

Modify `services/api/tests/billing/test_billing.py` in `test_checkout_returns_url_on_success` to assert configured URLs.

Add `monkeypatch` to the test parameters and set:

```python
monkeypatch.setenv("DOCPILOT_APP_URL", "https://bidpilot.rglens.com")
```

After the request, assert:

```python
_, kwargs = mock_checkout.call_args
assert kwargs["success_url"] == "https://bidpilot.rglens.com/projects?checkout=success"
assert kwargs["cancel_url"] == "https://bidpilot.rglens.com/pricing?checkout=cancelled"
```

- [ ] **Step 3: Run tests and confirm failure**

Run:

```powershell
uv run --directory services/api pytest tests/test_url_configuration.py tests/billing/test_billing.py -q
```

Expected:

- invitation or checkout assertions fail because localhost is hardcoded.

- [ ] **Step 4: Update email links**

Modify `services/api/app/email/service.py`.

Import:

```python
from app.core.settings import get_app_url
```

Replace module-level `APP_BASE_URL` usage with a helper:

```python
def _app_url() -> str:
    return get_app_url()
```

Use `_app_url()` inside each send function:

```python
reset_url = f"{_app_url()}/reset-password?token={token}"
verify_url = f"{_app_url()}/verify-email?token={token}"
link = f"{_app_url()}/register?invitation={token}"
```

For review links, use:

```python
project_url = f"{_app_url()}/projects"
```

- [ ] **Step 5: Update billing checkout links**

Modify `services/api/app/billing/router.py`.

Import:

```python
from app.core.settings import get_app_url
```

Before `create_checkout_session`, set:

```python
app_url = get_app_url()
```

Pass:

```python
success_url=f"{app_url}/projects?checkout=success",
cancel_url=f"{app_url}/pricing?checkout=cancelled",
```

- [ ] **Step 6: Verify tests**

Run:

```powershell
uv run --directory services/api pytest tests/test_url_configuration.py tests/billing/test_billing.py -q
```

Expected:

- all selected tests pass.

---

### Task 3: Strengthen Production Readiness Checks

**Files:**

- Modify: `scripts/production_readiness.py`
- Modify: `services/api/tests/test_production_readiness_script.py`
- Modify: `services/api/.env.example`
- Modify: `docs/development/configuration-and-secrets.md`

- [ ] **Step 1: Add failing readiness tests**

Modify `services/api/tests/test_production_readiness_script.py`.

Add to missing-required test assertions:

```python
assert "DOCPILOT_APP_URL is required" in result.errors
assert "DOCPILOT_CORS_ORIGINS is required" in result.errors
assert "DOCPILOT_LANGGRAPH_CHECKPOINTER must be postgres for production" in result.errors
```

Add a new test:

```python
def test_validate_environment_rejects_localhost_app_url_and_missing_smtp() -> None:
    env = {
        "DOCPILOT_DATABASE_URL": "postgresql+psycopg://docpilot:secret@db.internal:5432/docpilot",
        "DOCPILOT_REDIS_URL": "redis://redis.internal:6379/0",
        "DOCPILOT_MINIO_ENDPOINT": "s3.internal.example.com",
        "DOCPILOT_MINIO_ACCESS_KEY": "prod-access-key",
        "DOCPILOT_MINIO_SECRET_KEY": "prod-storage-secret",
        "DOCPILOT_JWT_SECRET": "prod-secret-value-with-more-than-thirty-two-bytes",
        "DOCPILOT_AUTH_REQUIRED": "true",
        "DOCPILOT_SECRETS_KEY": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        "DOCPILOT_PROVIDER_DOMESTIC_API_KEY": "prod-provider-key",
        "DOCPILOT_APP_URL": "http://localhost:5173",
        "DOCPILOT_CORS_ORIGINS": "http://localhost:5173",
        "DOCPILOT_LANGGRAPH_CHECKPOINTER": "memory",
    }

    result = production_readiness.validate_environment(env, target="production")

    assert result.ok is False
    assert "DOCPILOT_APP_URL must be https for production" in result.errors
    assert "DOCPILOT_APP_URL must not use localhost for production" in result.errors
    assert "DOCPILOT_CORS_ORIGINS must not use localhost for production" in result.errors
    assert "DOCPILOT_LANGGRAPH_CHECKPOINTER must be postgres for production" in result.errors
    assert "DOCPILOT_SMTP_HOST is required for production email" in result.errors
```

Update `test_validate_environment_accepts_production_ready_shape` env with:

```python
        "DOCPILOT_APP_URL": "https://bidpilot.rglens.com",
        "DOCPILOT_CORS_ORIGINS": "https://bidpilot.rglens.com",
"DOCPILOT_LANGGRAPH_CHECKPOINTER": "postgres",
"DOCPILOT_SMTP_HOST": "smtp.qq.com",
"DOCPILOT_SMTP_USER": "mailer@example.com",
        "DOCPILOT_SMTP_FROM": "noreply@rglens.com",
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
uv run --directory services/api pytest tests/test_production_readiness_script.py -q
```

Expected:

- tests fail because new validations do not exist.

- [ ] **Step 3: Implement readiness checks**

Modify `scripts/production_readiness.py`.

Add required variables:

```python
"DOCPILOT_APP_URL",
"DOCPILOT_CORS_ORIGINS",
"DOCPILOT_LANGGRAPH_CHECKPOINTER",
```

Add SMTP variables to production checks:

```python
SMTP_PRODUCTION_VARIABLES = [
    "DOCPILOT_SMTP_HOST",
    "DOCPILOT_SMTP_USER",
    "DOCPILOT_SMTP_FROM",
]
```

Add helper:

```python
def _is_https_url(value: str) -> bool:
    return value.lower().startswith("https://")
```

Inside `validate_environment`, for production target:

```python
app_url = env.get("DOCPILOT_APP_URL")
if app_url:
    if not _is_https_url(app_url):
        errors.append("DOCPILOT_APP_URL must be https for production")
    if _uses_localhost(app_url):
        errors.append("DOCPILOT_APP_URL must not use localhost for production")

cors = env.get("DOCPILOT_CORS_ORIGINS")
if cors and _uses_localhost(cors):
    errors.append("DOCPILOT_CORS_ORIGINS must not use localhost for production")
if app_url and cors and app_url.rstrip("/") not in [item.strip().rstrip("/") for item in cors.split(",")]:
    errors.append("DOCPILOT_CORS_ORIGINS must include DOCPILOT_APP_URL")

if env.get("DOCPILOT_LANGGRAPH_CHECKPOINTER") != "postgres":
    errors.append("DOCPILOT_LANGGRAPH_CHECKPOINTER must be postgres for production")

for name in SMTP_PRODUCTION_VARIABLES:
    if _is_missing(env.get(name)):
        errors.append(f"{name} is required for production email")
```

Add `ALIYUN_API_KEY` and `DASHSCOPE_API_KEY` to `PROVIDER_KEY_VARIABLES` if not present.

- [ ] **Step 4: Update examples/docs**

Modify `services/api/.env.example`:

```dotenv
DOCPILOT_APP_URL=http://localhost:5173
DOCPILOT_API_URL=http://localhost:8000
DOCPILOT_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Modify `docs/development/configuration-and-secrets.md` to document:

- `DOCPILOT_API_URL`
- `DOCPILOT_CORS_ORIGINS`
- production requires HTTPS `DOCPILOT_APP_URL`
- production requires `DOCPILOT_LANGGRAPH_CHECKPOINTER=postgres`

- [ ] **Step 5: Verify tests**

Run:

```powershell
uv run --directory services/api pytest tests/test_production_readiness_script.py -q
```

Expected:

- all production readiness tests pass.

---

### Task 4: Harden Project Org Access

**Files:**

- Modify: `services/api/app/projects/router.py`
- Modify: `services/api/app/projects/service.py`
- Modify: `services/api/app/projects/repository.py`
- Test: `services/api/tests/test_project_access.py`

- [ ] **Step 1: Write failing project access tests**

Create `services/api/tests/test_project_access.py`:

```python
import uuid

import pytest

from app.auth.schemas import CurrentUser
from app.auth.service import _hash_password
from app.db import SessionLocal
from app.main import app
from app.models import Organization, Project, User


def _make_org_user_and_project(db, slug: str):
    org = Organization(slug=slug, name=slug)
    db.add(org)
    db.flush()
    user = User(
        email=f"{slug}-{uuid.uuid4().hex[:8]}@example.com",
        display_name=slug,
        password_hash=_hash_password("Test1234"),
        role="member",
        email_verified=True,
        org_id=org.id,
    )
    db.add(user)
    project = Project(
        org_id=org.id,
        slug=f"{slug}-{uuid.uuid4().hex[:8]}",
        name=f"{slug} project",
        scenario_package="bidpilot",
    )
    db.add(project)
    db.commit()
    db.refresh(user)
    db.refresh(project)
    return org, user, project


@pytest.fixture
def isolated_users():
    db = SessionLocal()
    try:
        a = _make_org_user_and_project(db, "org-a")
        b = _make_org_user_and_project(db, "org-b")
        yield a, b
    finally:
        db.close()


def _override_user(user):
    async def dependency():
        return CurrentUser(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            plan="starter",
            email_verified=True,
            disabled=False,
            org_id=user.org_id,
            org_slug="",
        )

    return dependency


def test_get_project_rejects_cross_org_access(client, isolated_users):
    (_, user_a, _project_a), (_, _user_b, project_b) = isolated_users
    from app.auth.service import require_auth

    app.dependency_overrides[require_auth] = _override_user(user_a)
    try:
        response = client.get(f"/projects/{project_b.id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_update_and_delete_project_reject_cross_org_access(client, isolated_users):
    (_, user_a, _project_a), (_, _user_b, project_b) = isolated_users
    from app.auth.service import require_auth

    app.dependency_overrides[require_auth] = _override_user(user_a)
    try:
        patch_response = client.patch(f"/projects/{project_b.id}", json={"status": "archived"})
        delete_response = client.delete(f"/projects/{project_b.id}")
    finally:
        app.dependency_overrides.clear()

    assert patch_response.status_code == 404
    assert delete_response.status_code == 404
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
uv run --directory services/api pytest tests/test_project_access.py -q
```

Expected:

- tests fail because project detail/update/delete do not filter by org.

- [ ] **Step 3: Add org-aware repository helpers**

Modify `services/api/app/projects/repository.py`:

```python
def get_project_for_org(db: Session, project_id: str, org_id: str) -> Project | None:
    return db.scalar(select(Project).where(Project.id == project_id, Project.org_id == org_id))


def update_project_status_for_org(db: Session, project_id: str, org_id: str, status: str) -> Project | None:
    project = get_project_for_org(db, project_id, org_id)
    if project is None:
        return None
    project.status = status
    db.commit()
    db.refresh(project)
    return project


def delete_project_for_org(db: Session, project_id: str, org_id: str) -> bool:
    project = get_project_for_org(db, project_id, org_id)
    if project is None:
        return False
    db.delete(project)
    db.commit()
    return True
```

- [ ] **Step 4: Add org-aware service helpers**

Modify imports in `services/api/app/projects/service.py` to include the new repository helpers.

Add:

```python
def get_project_query_for_org(db: Session, project_id: str, org_id: str) -> ProjectRead | None:
    project = get_project_for_org(db, project_id, org_id)
    if project is None:
        return None
    return _project_to_read(project)


def update_project_status_command_for_org(db: Session, project_id: str, org_id: str, status: str) -> ProjectRead | None:
    project = update_project_status_for_org(db, project_id, org_id, status)
    if project is None:
        return None
    return _project_to_read(project)


def delete_project_command_for_org(db: Session, project_id: str, org_id: str) -> bool:
    return delete_project_for_org(db, project_id, org_id)
```

- [ ] **Step 5: Wire router to current user**

Modify `services/api/app/projects/router.py`.

Import new service functions.

Change `get_project` signature:

```python
def get_project(project_id: str, db: Session = Depends(get_db), current_user: CurrentUser = Depends(require_auth)) -> ProjectRead:
    result = get_project_query_for_org(db, project_id, current_user.org_id or "default")
```

Change `update_project` and `delete_project_endpoint` similarly to use current user's org.

- [ ] **Step 6: Verify project access tests**

Run:

```powershell
uv run --directory services/api pytest tests/test_project_access.py tests/test_plan_limits.py -q
```

Expected:

- tests pass.

---

### Task 5: Add Usage Ledger Model and Migration

**Files:**

- Modify: `services/api/app/models.py`
- Create: `services/api/alembic/versions/<new_revision>_add_usage_event_table.py`
- Create: `services/api/app/usage/__init__.py`
- Create: `services/api/app/usage/schemas.py`
- Create: `services/api/app/usage/service.py`
- Test: `services/api/tests/usage/test_usage_service.py`

- [ ] **Step 1: Write failing usage service tests**

Create directory `services/api/tests/usage`.

Create `services/api/tests/usage/test_usage_service.py`:

```python
from app.auth.service import _hash_password
from app.models import Organization, Project, Subscription, User
from app.usage.service import (
    ProviderSource,
    UsageLimitExceeded,
    check_workflow_quota,
    record_usage_event,
)


def _make_user_project(db, plan: str = "starter"):
    org = Organization(slug=f"usage-{plan}", name=f"Usage {plan}")
    db.add(org)
    db.flush()
    user = User(
        email=f"usage-{plan}@example.com",
        display_name="Usage User",
        password_hash=_hash_password("Test1234"),
        role="member",
        email_verified=True,
        org_id=org.id,
    )
    db.add(user)
    db.flush()
    db.add(Subscription(user_id=user.id, plan=plan, status="active"))
    project = Project(
        org_id=org.id,
        slug=f"usage-{plan}-project",
        name="Usage Project",
        scenario_package="bidpilot",
    )
    db.add(project)
    db.commit()
    db.refresh(user)
    db.refresh(project)
    return user, project


def test_starter_official_workflow_quota_allows_first_three(test_db):
    user, project = _make_user_project(test_db, "starter")

    for _ in range(3):
        check_workflow_quota(test_db, user.id, user.org_id, ProviderSource.OFFICIAL)
        record_usage_event(
            test_db,
            user_id=user.id,
            org_id=user.org_id,
            project_id=project.id,
            event_type="workflow_draft_started",
            provider_source=ProviderSource.OFFICIAL,
        )

    # The first three should not raise.


def test_starter_official_workflow_quota_blocks_fourth(test_db):
    user, project = _make_user_project(test_db, "starter")

    for _ in range(3):
        record_usage_event(
            test_db,
            user_id=user.id,
            org_id=user.org_id,
            project_id=project.id,
            event_type="workflow_draft_started",
            provider_source=ProviderSource.OFFICIAL,
        )

    try:
        check_workflow_quota(test_db, user.id, user.org_id, ProviderSource.OFFICIAL)
    except UsageLimitExceeded as exc:
        assert "starter workflow trial limit" in str(exc)
    else:
        raise AssertionError("Expected UsageLimitExceeded")


def test_professional_bypasses_starter_workflow_quota(test_db):
    user, project = _make_user_project(test_db, "professional")

    for _ in range(5):
        record_usage_event(
            test_db,
            user_id=user.id,
            org_id=user.org_id,
            project_id=project.id,
            event_type="workflow_draft_started",
            provider_source=ProviderSource.OFFICIAL,
        )

    check_workflow_quota(test_db, user.id, user.org_id, ProviderSource.OFFICIAL)


def test_byok_does_not_consume_official_workflow_quota(test_db):
    user, project = _make_user_project(test_db, "starter")

    for _ in range(5):
        record_usage_event(
            test_db,
            user_id=user.id,
            org_id=user.org_id,
            project_id=project.id,
            event_type="workflow_draft_started",
            provider_source=ProviderSource.BYOK,
        )

    check_workflow_quota(test_db, user.id, user.org_id, ProviderSource.OFFICIAL)
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
uv run --directory services/api pytest tests/usage/test_usage_service.py -q
```

Expected:

- fails because usage module/model does not exist.

- [ ] **Step 3: Add `UsageEvent` model**

Modify `services/api/app/models.py`.

Add after `Subscription` or near usage/accounting models:

```python
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
    metadata_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

- [ ] **Step 4: Add Alembic migration**

Create a new migration in `services/api/alembic/versions/`.

Use a unique revision id, for example `d1e2f3a4b5c6_add_usage_event_table.py`.

Migration body:

```python
"""add usage event table

Revision ID: d1e2f3a4b5c6
Revises: b4c5d6e7f8a9
Create Date: 2026-06-15
"""

from alembic import op
import sqlalchemy as sa


revision = "d1e2f3a4b5c6"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usage_event",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("organization.id"), nullable=False),
        sa.Column("project_id", sa.String(length=36), sa.ForeignKey("project.id"), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("provider_source", sa.String(length=30), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("execution_run_id", sa.String(length=36), sa.ForeignKey("execution_run.id"), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_usage_event_user_event_provider", "usage_event", ["user_id", "event_type", "provider_source"])
    op.create_index("ix_usage_event_org_created", "usage_event", ["org_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_usage_event_org_created", table_name="usage_event")
    op.drop_index("ix_usage_event_user_event_provider", table_name="usage_event")
    op.drop_table("usage_event")
```

If Alembic head differs when implementing, inspect `uv run --directory services/api alembic heads` and set `down_revision` to the actual current head.

- [ ] **Step 5: Add usage service**

Create `services/api/app/usage/__init__.py`:

```python
"""Usage accounting and quota enforcement."""
```

Create `services/api/app/usage/schemas.py`:

```python
from enum import StrEnum


class ProviderSource(StrEnum):
    OFFICIAL = "official"
    BYOK = "byok"
    STUB = "stub"
```

Create `services/api/app/usage/service.py`:

```python
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Subscription, UsageEvent

from .schemas import ProviderSource


STARTER_OFFICIAL_WORKFLOW_LIMIT = 3
WORKFLOW_DRAFT_STARTED = "workflow_draft_started"


class UsageLimitExceeded(ValueError):
    """Raised when a user exceeds a server-side usage limit."""


def get_user_plan(db: Session, user_id: str) -> str:
    sub = db.scalar(select(Subscription).where(Subscription.user_id == user_id))
    return sub.plan if sub else "starter"


def count_official_workflow_starts(db: Session, user_id: str) -> int:
    stmt = select(func.coalesce(func.sum(UsageEvent.units), 0)).where(
        UsageEvent.user_id == user_id,
        UsageEvent.event_type == WORKFLOW_DRAFT_STARTED,
        UsageEvent.provider_source == ProviderSource.OFFICIAL.value,
    )
    return int(db.scalar(stmt) or 0)


def check_workflow_quota(
    db: Session,
    user_id: str,
    org_id: str,
    provider_source: ProviderSource,
) -> None:
    if provider_source != ProviderSource.OFFICIAL:
        return
    plan = get_user_plan(db, user_id)
    if plan in {"professional", "enterprise"}:
        return
    used = count_official_workflow_starts(db, user_id)
    if used >= STARTER_OFFICIAL_WORKFLOW_LIMIT:
        raise UsageLimitExceeded(
            f"starter workflow trial limit of {STARTER_OFFICIAL_WORKFLOW_LIMIT} official runs has been reached"
        )


def record_usage_event(
    db: Session,
    *,
    user_id: str,
    org_id: str,
    event_type: str,
    provider_source: ProviderSource,
    project_id: str | None = None,
    execution_run_id: str | None = None,
    units: int = 1,
    metadata_json: dict | None = None,
) -> UsageEvent:
    event = UsageEvent(
        user_id=user_id,
        org_id=org_id,
        project_id=project_id,
        event_type=event_type,
        provider_source=provider_source.value,
        execution_run_id=execution_run_id,
        units=units,
        metadata_json=metadata_json,
    )
    db.add(event)
    db.flush()
    return event
```

- [ ] **Step 6: Verify usage service tests**

Run:

```powershell
uv run --directory services/api pytest tests/usage/test_usage_service.py -q
```

Expected:

- usage service tests pass.

---

### Task 6: Enforce Workflow Quota Before Draft Enqueue

**Files:**

- Modify: `services/api/app/drafting/service.py`
- Modify: `services/api/app/drafting/router.py`
- Modify: `services/api/app/assistant/tools.py`
- Test: `services/api/tests/drafting/test_workflow_quota.py`
- Test: `services/api/tests/assistant/test_assistant_harness.py`

- [ ] **Step 1: Write failing drafting quota tests**

Create `services/api/tests/drafting/test_workflow_quota.py`:

```python
import uuid
from unittest.mock import patch

from app.auth.service import _hash_password
from app.db import SessionLocal
from app.models import Organization, Project, Subscription, User
from app.usage.schemas import ProviderSource
from app.usage.service import record_usage_event


def _make_user_project(plan: str = "starter"):
    db = SessionLocal()
    try:
        org = Organization(slug=f"quota-{uuid.uuid4().hex[:8]}", name="Quota Org")
        db.add(org)
        db.flush()
        user = User(
            email=f"quota-{uuid.uuid4().hex[:8]}@example.com",
            display_name="Quota User",
            password_hash=_hash_password("Test1234"),
            role="member",
            email_verified=True,
            org_id=org.id,
        )
        db.add(user)
        db.flush()
        db.add(Subscription(user_id=user.id, plan=plan, status="active"))
        project = Project(
            org_id=org.id,
            slug=f"quota-project-{uuid.uuid4().hex[:8]}",
            name="Quota Project",
            scenario_package="bidpilot",
        )
        db.add(project)
        db.commit()
        db.refresh(user)
        db.refresh(project)
        return user.id, user.org_id, project.id
    finally:
        db.close()


def test_draft_section_blocks_starter_fourth_official_run(client):
    user_id, org_id, project_id = _make_user_project("starter")
    db = SessionLocal()
    try:
        for _ in range(3):
            record_usage_event(
                db,
                user_id=user_id,
                org_id=org_id,
                project_id=project_id,
                event_type="workflow_draft_started",
                provider_source=ProviderSource.OFFICIAL,
            )
        db.commit()
    finally:
        db.close()

    with patch("app.auth.service.get_dev_user") as mock_dev_user:
        from app.auth.schemas import CurrentUser

        mock_dev_user.return_value = CurrentUser(
            id=user_id,
            email="quota@example.com",
            display_name="Quota User",
            role="member",
            plan="starter",
            org_id=org_id,
            org_slug="",
            email_verified=True,
            disabled=False,
        )
        response = client.post(
            "/drafting/sections",
            json={"project_id": project_id, "section_key": "technical-approach"},
        )

    assert response.status_code in (403, 429)
    assert "starter workflow trial limit" in response.text


def test_draft_section_records_usage_before_enqueue(client):
    user_id, org_id, project_id = _make_user_project("starter")

    with patch("app.celery_client.celery.send_task") as mock_send_task:
        with patch("app.auth.service.get_dev_user") as mock_dev_user:
            from app.auth.schemas import CurrentUser

            mock_dev_user.return_value = CurrentUser(
                id=user_id,
                email="quota@example.com",
                display_name="Quota User",
                role="member",
                plan="starter",
                org_id=org_id,
                org_slug="",
                email_verified=True,
                disabled=False,
            )
            response = client.post(
                "/drafting/sections",
                json={"project_id": project_id, "section_key": "technical-approach"},
            )

    assert response.status_code == 202
    assert mock_send_task.called

    db = SessionLocal()
    try:
        from app.models import UsageEvent

        events = db.query(UsageEvent).filter_by(user_id=user_id, event_type="workflow_draft_started").all()
        assert len(events) == 1
        assert events[0].provider_source == "official"
    finally:
        db.close()
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
uv run --directory services/api pytest tests/drafting/test_workflow_quota.py -q
```

Expected:

- tests fail because drafting service does not enforce usage quota.

- [ ] **Step 3: Add user context to drafting service**

Modify `services/api/app/drafting/service.py`.

Import:

```python
from app.auth.schemas import CurrentUser
from app.usage.schemas import ProviderSource
from app.usage.service import (
    WORKFLOW_DRAFT_STARTED,
    UsageLimitExceeded,
    check_workflow_quota,
    record_usage_event,
)
```

Add helper:

```python
def _provider_source(provider_config_id: str | None) -> ProviderSource:
    return ProviderSource.BYOK if provider_config_id else ProviderSource.OFFICIAL
```

Change signatures:

```python
def draft_section_command(db: Session, payload: DraftSectionRequest, current_user: CurrentUser | None = None) -> DraftSectionResponse:
```

And for redraft.

Before creating `ExecutionRun`, if `current_user` is not None:

```python
provider_source = _provider_source(payload.provider_config_id)
check_workflow_quota(db, current_user.id, current_user.org_id, provider_source)
```

After creating the run and before sending Celery task:

```python
if current_user is not None:
    record_usage_event(
        db,
        user_id=current_user.id,
        org_id=current_user.org_id,
        project_id=payload.project_id,
        event_type=WORKFLOW_DRAFT_STARTED,
        provider_source=provider_source,
        execution_run_id=run.id,
    )
```

Do the same for `redraft_section_command`.

- [ ] **Step 4: Wire router current user and error**

Modify `services/api/app/drafting/router.py`.

Import:

```python
from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.usage.service import UsageLimitExceeded
```

Change draft/redraft endpoints to accept:

```python
current_user: CurrentUser = Depends(require_auth)
```

Call:

```python
return draft_section_command(db, payload, current_user)
```

Wrap quota errors:

```python
try:
    return draft_section_command(db, payload, current_user)
except UsageLimitExceeded as exc:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
```

- [ ] **Step 5: Wire assistant tool current user**

Modify `services/api/app/assistant/tools.py`.

Change:

```python
if tool_name == "start_draft_section":
    return start_draft_section(db, user, arguments)
if tool_name == "start_redraft_section":
    return start_redraft_section(db, user, arguments)
```

Change function signatures:

```python
def start_draft_section(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
```

Call:

```python
response = draft_section_command(db, DraftSectionRequest(...), user)
```

Do the same for redraft.

- [ ] **Step 6: Verify quota tests**

Run:

```powershell
uv run --directory services/api pytest tests/drafting/test_workflow_quota.py tests/assistant/test_assistant_harness.py -q
```

Expected:

- tests pass, or existing assistant tests are updated for the new call signature.

---

### Task 7: Frontend Quota Error Display

**Files:**

- Modify: `apps/web/src/features/projects/project-detail-page.tsx`
- Modify: `apps/web/src/lib/api.ts` if error extraction is insufficient.
- Test: add or update existing project/detail test if available.

- [ ] **Step 1: Inspect current drafting mutation error handling**

Run:

```powershell
rg "draftMut|redraftMut|drafting/sections|toast.error" apps/web/src/features/projects/project-detail-page.tsx apps/web/src/lib/api.ts -n
```

Expected:

- identify the existing toast/error handling around draft and redraft buttons.

- [ ] **Step 2: Update quota error text**

If `api.ts` throws an error with a backend detail, keep the existing helper. If it only throws generic text, update it to preserve backend `message` or `detail`.

In `project-detail-page.tsx`, map quota text to a user-facing message:

```ts
const quotaMessage =
  i18n.language.startsWith("zh")
    ? "免费试用的 AI 起草次数已用完。可以切换到自定义模型 Key，或升级账号后继续。"
    : "Your free AI drafting trial runs are used up. Connect your own provider key or upgrade to continue.";
```

When mutation catches an error containing `starter workflow trial limit`, show `quotaMessage`.

- [ ] **Step 3: Add i18n keys if needed**

Prefer locale keys under existing project/drafting namespace:

```json
"quotaReached": "免费试用的 AI 起草次数已用完。可以切换到自定义模型 Key，或升级账号后继续。"
```

English:

```json
"quotaReached": "Your free AI drafting trial runs are used up. Connect your own provider key or upgrade to continue."
```

- [ ] **Step 4: Run frontend verification**

Run:

```powershell
pnpm --filter @docpilot/web test -- --run
pnpm --filter @docpilot/web build
```

Expected:

- tests pass;
- build succeeds.

---

### Task 8: Deployment Packaging and VPS Runbook

**Files:**

- Modify: `compose.yml`
- Create: `services/api/Dockerfile`
- Create: `services/worker/Dockerfile`
- Create: `apps/web/Dockerfile` or document static build via 1Panel if choosing mixed deployment.
- Create: `docs/ops/vps-pilot-deployment.md`
- Modify: `docs/ops/deployment-and-runbook.md`
- Modify: `docs/ops/release-checklist.md`

- [ ] **Step 1: Decide packaging path**

Recommended path:

- extend `compose.yml` for `api` and `worker`;
- serve web static files through 1Panel site or an Nginx container.

If using 1Panel static site for web, do not add `apps/web/Dockerfile`; document build/upload path in `docs/ops/vps-pilot-deployment.md`.

- [ ] **Step 2: Add API Dockerfile**

Create `services/api/Dockerfile`:

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

COPY services/api/pyproject.toml /app/pyproject.toml
COPY uv.lock /app/uv.lock
RUN uv sync --frozen --no-dev

COPY services/api/app /app/app
COPY services/api/alembic.ini /app/alembic.ini
COPY services/api/alembic /app/alembic

ENV PYTHONPATH=/app
EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

If the Docker build context is `services/api` instead of repo root, adjust `COPY` paths accordingly and document the exact build command.

- [ ] **Step 3: Add Worker Dockerfile**

Create `services/worker/Dockerfile`:

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

COPY services/worker/pyproject.toml /app/pyproject.toml
COPY uv.lock /app/uv.lock
RUN uv sync --frozen --no-dev

COPY services/worker/app /app/app

ENV PYTHONPATH=/app

CMD ["uv", "run", "celery", "-A", "app.celery_app", "worker", "--loglevel=info"]
```

- [ ] **Step 4: Extend compose carefully**

Modify `compose.yml` to add:

```yaml
  api:
    build:
      context: .
      dockerfile: services/api/Dockerfile
    restart: unless-stopped
    env_file:
      - .env.production
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
      minio:
        condition: service_started
    ports:
      - "8000:8000"

  worker:
    build:
      context: .
      dockerfile: services/worker/Dockerfile
    restart: unless-stopped
    env_file:
      - .env.production
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
      minio:
        condition: service_started
```

Do not commit `.env.production`.

- [ ] **Step 5: Document VPS pilot deployment**

Create `docs/ops/vps-pilot-deployment.md` with these sections:

- prerequisites: Docker, Docker Compose, Node/pnpm for web build if static site;
- DNS and HTTPS domains;
- required environment variables;
- `.env.production` template with placeholder values only;
- build and start commands;
- migration command;
- first admin bootstrap;
- web build/deploy command;
- reverse proxy mapping;
- health checks;
- backup command;
- rollback command.

Use commands in Windows/local and Linux/VPS form where appropriate. Do not include real secrets.

- [ ] **Step 6: Update runbook and release checklist**

Modify `docs/ops/deployment-and-runbook.md` to link the new VPS pilot runbook.

Modify `docs/ops/release-checklist.md` to include:

- production readiness script with VPS env;
- email link verification;
- starter quota verification;
- backup restore drill;
- public API/web health.

- [ ] **Step 7: Validate Dockerfiles/compose syntax if Docker is available**

Run:

```powershell
docker compose -f compose.yml config
```

Expected:

- compose config renders successfully.

If Docker is not available, record that verification was not run.

---

### Task 9: Known Limitations and Pilot Docs Update

**Files:**

- Modify: `docs/product/known-limitations.md`
- Modify: `docs/product/pilot-readiness-checklist.md`
- Modify: `docs/product/pilot-commercial-readiness.md` if owner fields need final decision.

- [ ] **Step 1: Update known limitations**

Ensure `docs/product/known-limitations.md` says:

- pilot is controlled, not open public launch;
- starter official workflow trial is 3 runs;
- assistant chat is beta/free but rate-limited or operationally monitored;
- Stripe remains scaffolded unless live keys and billing flow are explicitly enabled;
- large document bundles are not yet guaranteed;
- MinIO/DB backups must be verified per VPS runbook.

- [ ] **Step 2: Update readiness checklist**

Modify `docs/product/pilot-readiness-checklist.md` to remove over-optimistic `[x]` items if they are not proven on the actual VPS.

Use wording like:

```markdown
- [ ] VPS pilot deployment passes production readiness with real deployment env.
- [ ] Deployed E2E flow passes on public HTTPS URLs.
- [ ] Starter workflow quota blocks the 4th official-provider draft run.
```

- [ ] **Step 3: No test required**

Docs-only task. Run:

```powershell
rg "VPS pilot|workflow trial|Stripe|known limitations" docs/product -n
```

Expected:

- updated docs include the new pilot constraints.

---

### Task 10: Final Verification Gate

**Files:**

- No new files unless failures require fixes.

- [ ] **Step 1: Run backend focused tests**

Run:

```powershell
uv run --directory services/api pytest tests/test_runtime_settings.py tests/test_url_configuration.py tests/test_production_readiness_script.py tests/test_project_access.py tests/usage/test_usage_service.py tests/drafting/test_workflow_quota.py tests/billing/test_billing.py tests/assistant/test_assistant_harness.py -q
```

Expected:

- all selected backend tests pass.

- [ ] **Step 2: Run broader backend smoke tests**

Run:

```powershell
uv run --directory services/api pytest tests/test_openapi_smoke.py tests/chat/test_chat.py tests/providers/test_providers_api.py tests/export/test_export_docx.py tests/export/test_pdf_export.py -q
```

Expected:

- all selected smoke tests pass.

- [ ] **Step 3: Run worker tests**

Run:

```powershell
uv run --directory services/worker pytest tests/test_adapters.py tests/test_graph_integration.py tests/test_supervisor.py tests/test_section_drafter.py -q
```

Expected:

- worker tests pass.

- [ ] **Step 4: Run frontend tests and build**

Run:

```powershell
pnpm --filter @docpilot/web test -- --run
pnpm --filter @docpilot/web build
```

Expected:

- tests pass;
- build succeeds.

- [ ] **Step 5: Run production readiness tests**

Run with a fake complete env, never real secrets printed:

```powershell
$env:DOCPILOT_DATABASE_URL="postgresql+psycopg://docpilot:secret@db.internal:5432/docpilot"
$env:DOCPILOT_REDIS_URL="redis://redis.internal:6379/0"
$env:DOCPILOT_MINIO_ENDPOINT="s3.internal.example.com"
$env:DOCPILOT_MINIO_ACCESS_KEY="prod-access-key"
$env:DOCPILOT_MINIO_SECRET_KEY="prod-storage-secret"
$env:DOCPILOT_JWT_SECRET="prod-secret-value-with-more-than-thirty-two-bytes"
$env:DOCPILOT_AUTH_REQUIRED="true"
$env:DOCPILOT_SECRETS_KEY="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
$env:DOCPILOT_PROVIDER_DOMESTIC_API_KEY="fake-provider-key"
$env:DOCPILOT_APP_URL="https://bidpilot.rglens.com"
$env:DOCPILOT_CORS_ORIGINS="https://bidpilot.rglens.com"
$env:DOCPILOT_LANGGRAPH_CHECKPOINTER="postgres"
$env:DOCPILOT_SMTP_HOST="smtp.qq.com"
$env:DOCPILOT_SMTP_USER="mailer@example.com"
$env:DOCPILOT_SMTP_FROM="noreply@rglens.com"
python scripts/production_readiness.py --target production
```

Expected:

- `production readiness check passed`.

- [ ] **Step 6: Search for accidental secret or localhost leakage**

Run:

```powershell
rg "sk-|ALIYUN_API_KEY=.+|DASHSCOPE_API_KEY=.+|DOCPILOT_PROVIDER_DOMESTIC_API_KEY=.+|http://localhost:5173" services apps scripts docs -n
```

Expected:

- no real secrets;
- `http://localhost:5173` only appears in local defaults, tests, or local docs.

---

## Handoff Notes for the Next Model

- Do not print or inspect real API key values.
- The user intentionally wants official provider keys server-side only.
- BYOK keys must remain encrypted with `DOCPILOT_SECRETS_KEY`.
- Keep paid Stripe self-serve out of this phase.
- Prefer backend enforcement over UI-only blocking.
- If a migration head conflict appears, inspect Alembic heads and create/adjust a merge revision rather than deleting migrations.
- Worktree is already dirty with many prior changes; do not revert unrelated files.
- Use `apply_patch` for manual edits.

## Completion Criteria

This plan is complete when:

- production URL configuration is implemented;
- production readiness rejects unsafe pilot envs;
- project org access is hardened for detail/update/delete;
- usage ledger exists and starter workflow quota is enforced server-side;
- docs and VPS runbook describe the exact pilot deployment path;
- focused backend, worker, and frontend checks pass;
- no secrets are exposed in files or logs.
