import os
import sys
from pathlib import Path

import pytest


# Configure a dedicated test database before any application module can create
# an engine. CI already supplies docpilot_test; local runs must opt in.
api_root = Path(__file__).resolve().parent.parent
repo_root = api_root.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from scripts.test_database_safety import UnsafeTestDatabaseError, resolve_test_database_url  # noqa: E402

try:
    _test_database_url = resolve_test_database_url(os.environ)
except UnsafeTestDatabaseError as exc:
    pytest.exit(str(exc), returncode=2)
os.environ["DOCPILOT_DATABASE_URL"] = _test_database_url
os.environ["DOCPILOT_TEST_DATABASE_URL"] = _test_database_url

# API tests exercise deterministic in-memory auth throttles. Redis itself is
# started in CI for queue/integration coverage, but must not leak into auth's
# module-level limiter selection before the test fixtures import that module.
os.environ.pop("DOCPILOT_REDIS_URL", None)
os.environ.pop("DOCPILOT_RATE_LIMIT_STORAGE_URI", None)

# Disable structlog JSON output during tests
os.environ["DOCPILOT_LOGGING"] = "off"

# High rate limit for test suite (136+ tests, each may make multiple requests)
os.environ["DOCPILOT_RATE_LIMIT"] = "10000/minute"

# Stable Fernet key for test-only provider secret encryption.
os.environ["DOCPILOT_SECRETS_KEY"] = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="

# Keep assistant endpoint deterministic in tests. Production defaults to the
# governed Harness, but tests must never call external model providers.
for _provider_env_name in (
    "LLM_API_KEY",
    "LLM_API_URL",
    "LLM_MODEL",
    "OPENCODE_API_KEY",
    "OPENCODE_BASE_URL",
    "OPENCODE_MODEL",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_MODEL",
    "DOCPILOT_PROVIDER_DOMESTIC_API_KEY",
    "DOCPILOT_PROVIDER_DOMESTIC_BASE_URL",
    "DOCPILOT_LLM_MODEL_PRIMARY",
    "ALIYUN_API_KEY",
    "DASHSCOPE_API_KEY",
    "DOCPILOT_PROVIDER_OPENAI_API_KEY",
    "DOCPILOT_PROVIDER_OPENAI_BASE_URL",
    "OPENAI_API_KEY",
):
    os.environ.pop(_provider_env_name, None)

# New assistant turns always use the Pi sidecar. Tests that exercise the
# stream mock the sidecar boundary or assert its fail-safe SSE response.
os.environ["DOCPILOT_ASSISTANT_ENGINE"] = "pi"
os.environ["DOCPILOT_ASSISTANT_API_KEY"] = "test-assistant-key"
os.environ["DOCPILOT_ASSISTANT_PROTOCOL"] = "openai"
os.environ["DOCPILOT_ASSISTANT_PROVIDER_ID"] = "test"
os.environ["DOCPILOT_ASSISTANT_BASE_URL"] = "https://models.example.test/v1"
os.environ["DOCPILOT_ASSISTANT_MODEL"] = "test-assistant-model"

# Disable auth requirement in tests (uses dev fallback)
# Must happen before app modules are imported
os.environ.pop("DOCPILOT_AUTH_REQUIRED", None)

# Force console email backend in tests (don't hit real SMTP)
for _smtp_env_name in (
    "DOCPILOT_SMTP_HOST",
    "DOCPILOT_SMTP_USER",
    "DOCPILOT_SMTP_PASS",
    "DOCPILOT_SMTP_FROM",
    "DOCPILOT_SMTP_FROM_NAME",
    "DOCPILOT_SMTP_PORT",
    "DOCPILOT_SMTP_TLS",
    "DOCPILOT_RESEND_API_KEY",
    "DOCPILOT_RESEND_FROM",
    "DOCPILOT_RESEND_API_URL",
    "RESEND_API_KEY",
    "resend_api_key",
):
    os.environ.pop(_smtp_env_name, None)

# Ensure the app package is importable from the services/api root
if str(api_root) not in sys.path:
    sys.path.insert(0, str(api_root))

# Ensure shared packages are importable
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# Reset module-level AUTH_REQUIRED flag that may have been set during import
try:
    from app.auth import service as _auth_service
    _auth_service.AUTH_REQUIRED = False
except ImportError:
    pass

# Reset email backend to console (SMTP vars cleared above)
try:
    from app.email import service as _email_service
    _email_service._backend = None
    _email_service.SMTP_CONFIGURED = False
    _email_service.RESEND_CONFIGURED = False
except ImportError:
    pass


@pytest.fixture
def client():
    """Provide a FastAPI TestClient."""
    from app.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_usage_events():
    """Prevent shared dev-user quota counters from leaking across tests."""
    from sqlalchemy import delete

    from app.db import SessionLocal
    from app.models import (
        ModelUsageRecord,
        ModelUsageReservation,
        OrganizationUsageBudget,
        OrganizationUsageBudgetEvent,
        UsageEvent,
    )

    db = SessionLocal()
    try:
        db.execute(delete(ModelUsageRecord))
        db.execute(delete(ModelUsageReservation))
        db.execute(delete(OrganizationUsageBudgetEvent))
        db.execute(delete(OrganizationUsageBudget))
        db.execute(delete(UsageEvent))
        db.commit()
        yield
    finally:
        db.execute(delete(ModelUsageRecord))
        db.execute(delete(ModelUsageReservation))
        db.execute(delete(OrganizationUsageBudgetEvent))
        db.execute(delete(OrganizationUsageBudget))
        db.execute(delete(UsageEvent))
        db.commit()
        db.close()


@pytest.fixture(autouse=True)
def reset_notifications():
    """Keep the notification inbox isolated across API tests."""
    from sqlalchemy import delete

    from app.db import SessionLocal
    from app.models import Notification, NotificationPreference

    db = SessionLocal()
    try:
        db.execute(delete(Notification))
        db.execute(delete(NotificationPreference))
        db.commit()
        yield
    finally:
        db.execute(delete(Notification))
        db.execute(delete(NotificationPreference))
        db.commit()
        db.close()


@pytest.fixture(autouse=True)
def reset_auth_rate_limiter_state():
    """Keep local in-memory auth budgets isolated between test cases."""
    from app.auth import service as auth_service

    limiters = (
        auth_service.login_rate_limiter,
        auth_service.resend_rate_limiter,
        auth_service.registration_rate_limiter,
        auth_service.password_reset_rate_limiter,
    )
    for limiter in limiters:
        attempts = getattr(limiter, "_attempts", None)
        if attempts is not None:
            attempts.clear()
    yield
    for limiter in limiters:
        attempts = getattr(limiter, "_attempts", None)
        if attempts is not None:
            attempts.clear()


@pytest.fixture
def test_db():
    """Provide a SQLAlchemy session for direct service-layer tests."""
    from app.db import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


@pytest.fixture
def default_org_id() -> str:
    """Ensure the default organization exists and return its stable UUID."""
    from app.db import SessionLocal
    from app.models import Organization
    db = SessionLocal()
    try:
        org = db.query(Organization).filter_by(slug="default").first()
        if org is None:
            org = Organization(id="00000000-0000-0000-0000-000000000001", slug="default", name="Default Organization")
            db.add(org)
            db.commit()
            db.refresh(org)
        return org.id
    finally:
        db.close()


DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def default_user_id(default_org_id: str) -> str:
    """Ensure the dev fallback user exists in the DB and return its stable UUID.

    The auth service's get_dev_user() returns CurrentUser(id='dev-user', ...).
    This fixture creates a matching User row so FK constraints (e.g. provider_config.user_id) pass.
    """
    from app.db import SessionLocal
    from app.models import OrganizationMembership, User
    import bcrypt

    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id="dev-user").first()
        if user is None:
            user = User(
                id="dev-user",
                email="dev@docpilot.local",
                display_name="Dev User",
                role="admin",
                org_id=default_org_id,
                password_hash=bcrypt.hashpw(b"dummy", bcrypt.gensalt()).decode(),
            )
            db.add(user)
            db.flush()
        membership = db.query(OrganizationMembership).filter_by(
            org_id=default_org_id,
            user_id=user.id,
        ).first()
        if membership is None:
            db.add(
                OrganizationMembership(
                    org_id=default_org_id,
                    user_id=user.id,
                    role="owner",
                )
            )
        elif membership.status != "active":
            membership.status = "active"
            membership.removed_at = None
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()
