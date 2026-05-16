import uuid

import pytest

from app.auth.service import bootstrap_admin_command
from app.db import SessionLocal


def _email() -> str:
    return f"admin-{uuid.uuid4().hex[:8]}@docpilot.local"


def test_bootstrap_admin_creates_admin_when_user_missing() -> None:
    db = SessionLocal()
    try:
        email = _email()
        result = bootstrap_admin_command(db, email=email, display_name="Pilot Admin", password="secret123")

        assert result.status == "created"
        assert result.user.email == email
        assert result.user.role == "admin"
    finally:
        db.close()


def test_bootstrap_admin_is_idempotent_when_admin_already_exists() -> None:
    db = SessionLocal()
    try:
        email = _email()
        first = bootstrap_admin_command(db, email=email, display_name="Pilot Admin", password="secret123")
        second = bootstrap_admin_command(db, email=email, display_name="Pilot Admin", password="secret123")

        assert first.status == "created"
        assert second.status == "already_admin"
        assert second.user.id == first.user.id
        assert second.user.role == "admin"
    finally:
        db.close()


def test_bootstrap_admin_refuses_to_promote_member_without_flag() -> None:
    db = SessionLocal()
    try:
        email = _email()
        # Existing member user (default role is "member")
        from app.auth.repository import create_user
        from app.models import User

        create_user(
            db,
            User(email=email, display_name="Existing Member", password_hash="x", role="member",
                 org_id="00000000-0000-0000-0000-000000000001"),
        )

        with pytest.raises(ValueError, match="not an admin"):
            bootstrap_admin_command(db, email=email, display_name="Existing Member", password="secret123")
    finally:
        db.close()


def test_bootstrap_admin_promotes_member_with_flag() -> None:
    db = SessionLocal()
    try:
        email = _email()
        from app.auth.repository import create_user
        from app.models import User

        create_user(
            db,
            User(email=email, display_name="Existing Member", password_hash="x", role="member",
                 org_id="00000000-0000-0000-0000-000000000001"),
        )

        result = bootstrap_admin_command(
            db,
            email=email,
            display_name="Existing Member",
            password="secret123",
            promote=True,
        )

        assert result.status == "promoted"
        assert result.user.role == "admin"
    finally:
        db.close()
