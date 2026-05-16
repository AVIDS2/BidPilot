"""Test server-side refresh token storage."""
import hashlib
import uuid

from app.auth.schemas import UserRegister
from app.auth.service import register_user_command, login_command, refresh_token_command
from app.models import RefreshToken, User


def _unique_suffix() -> str:
    return uuid.uuid4().hex[:6]


def test_login_stores_refresh_token(test_db):
    """Login should store a hashed refresh token in DB."""
    suffix = _unique_suffix()
    email = f"rt-test-{suffix}@docpilot.ai"
    payload = UserRegister(email=email, display_name="RT Test", password="Test1234")
    register_user_command(test_db, payload)
    u = test_db.query(User).filter_by(email=email).first()
    u.email_verified = True
    test_db.commit()

    result = login_command(test_db, email, "Test1234")
    assert result.refresh_token is not None

    # Check DB for stored token
    token_hash = hashlib.sha256(result.refresh_token.encode()).hexdigest()
    stored = test_db.query(RefreshToken).filter_by(token_hash=token_hash).first()
    assert stored is not None
    assert stored.user_id == u.id
    assert not stored.revoked


def test_refresh_token_validates_against_db(test_db):
    """Refresh should succeed only if token exists in DB and is not revoked."""
    suffix = _unique_suffix()
    email = f"rt-test2-{suffix}@docpilot.ai"
    payload = UserRegister(email=email, display_name="RT Test 2", password="Test1234")
    register_user_command(test_db, payload)
    u = test_db.query(User).filter_by(email=email).first()
    u.email_verified = True
    test_db.commit()

    result = login_command(test_db, email, "Test1234")
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
    suffix = _unique_suffix()
    email = f"rt-test3-{suffix}@docpilot.ai"
    payload = UserRegister(email=email, display_name="RT Test 3", password="Test1234")
    register_user_command(test_db, payload)
    u = test_db.query(User).filter_by(email=email).first()
    u.email_verified = True
    test_db.commit()

    # Login to get a real token stored in DB
    result = login_command(test_db, email, "Test1234")
    token = result.refresh_token

    # Manually expire the DB record (use naive datetime to match DB column type)
    from datetime import UTC, datetime, timedelta
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stored = test_db.query(RefreshToken).filter_by(token_hash=token_hash).first()
    stored.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    test_db.commit()

    import pytest
    with pytest.raises(ValueError, match="expired"):
        refresh_token_command(test_db, token)
