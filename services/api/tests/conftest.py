import os
import sys
from pathlib import Path

import pytest

# Disable structlog JSON output during tests
os.environ["DOCPILOT_LOGGING"] = "off"

# High rate limit for test suite (136+ tests, each may make multiple requests)
os.environ["DOCPILOT_RATE_LIMIT"] = "10000/minute"

# Stable Fernet key for test-only provider secret encryption.
os.environ["DOCPILOT_SECRETS_KEY"] = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="

# Keep assistant endpoint deterministic in tests. Production defaults to the
# LangGraph engine, but tests must never call external model providers.
os.environ["DOCPILOT_ASSISTANT_ENGINE"] = "deterministic"

# Disable auth requirement in tests (uses dev fallback)
# Must happen before app modules are imported
os.environ.pop("DOCPILOT_AUTH_REQUIRED", None)

# Force console email backend in tests (don't hit real SMTP)
os.environ.pop("DOCPILOT_SMTP_HOST", None)
os.environ.pop("DOCPILOT_SMTP_USER", None)

# Ensure the app package is importable from the services/api root
api_root = Path(__file__).resolve().parent.parent
if str(api_root) not in sys.path:
    sys.path.insert(0, str(api_root))

# Ensure shared packages are importable
repo_root = api_root.parent.parent
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
except ImportError:
    pass


@pytest.fixture
def client():
    """Provide a FastAPI TestClient."""
    from app.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)


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
    from app.models import User
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
            db.commit()
            db.refresh(user)
        return user.id
    finally:
        db.close()
