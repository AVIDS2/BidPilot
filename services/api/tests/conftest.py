import os
import sys
from pathlib import Path

import pytest

# Disable structlog JSON output during tests
os.environ["DOCPILOT_LOGGING"] = "off"

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
