import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.schemas import CurrentUser
from app.auth.service import _hash_password, require_auth
from app.db import Base, get_db
from app.main import app
from app.models import Organization, Subscription, UsageEvent, User
from app.usage.schemas import ProviderSource
from app.usage.service import ASSISTANT_MESSAGE_STARTED, record_usage_event


def _make_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return SessionLocal


def _make_user(SessionLocal, plan: str = "starter") -> User:
    db = SessionLocal()
    try:
        org = Organization(slug=f"assistant-usage-{uuid.uuid4().hex[:8]}", name="Assistant Usage")
        db.add(org)
        db.flush()
        user = User(
            email=f"assistant-usage-{uuid.uuid4().hex[:8]}@example.com",
            display_name="Assistant Usage",
            password_hash=_hash_password("Test1234"),
            role="member",
            email_verified=True,
            org_id=org.id,
        )
        db.add(user)
        db.flush()
        db.add(Subscription(user_id=user.id, plan=plan, status="active"))
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def _override_user(user: User):
    async def dependency():
        return CurrentUser(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            plan="starter",
            org_id=user.org_id,
            org_slug="",
            email_verified=True,
            disabled=False,
        )

    return dependency


def _override_get_db(SessionLocal):
    def dependency():
        with SessionLocal() as session:
            yield session

    return dependency


def test_assistant_stream_records_official_usage(client):
    SessionLocal = _make_db()
    user = _make_user(SessionLocal)
    try:
        app.dependency_overrides[get_db] = _override_get_db(SessionLocal)
        app.dependency_overrides[require_auth] = _override_user(user)

        response = client.post("/assistant/stream", json={"message": "你好"})
        assert response.status_code == 200

        with SessionLocal() as db:
            events = db.query(UsageEvent).filter_by(
                user_id=user.id,
                event_type=ASSISTANT_MESSAGE_STARTED,
            ).all()
            assert len(events) == 1
            assert events[0].provider_source == ProviderSource.OFFICIAL.value
            assert events[0].units == 1
    finally:
        app.dependency_overrides.clear()


def test_assistant_stream_blocks_starter_after_official_limit(client):
    SessionLocal = _make_db()
    user = _make_user(SessionLocal)
    with SessionLocal() as db:
        for _ in range(100):
            record_usage_event(
                db,
                user_id=user.id,
                org_id=user.org_id,
                event_type=ASSISTANT_MESSAGE_STARTED,
                provider_source=ProviderSource.OFFICIAL,
            )
        db.commit()

    try:
        app.dependency_overrides[get_db] = _override_get_db(SessionLocal)
        app.dependency_overrides[require_auth] = _override_user(user)

        response = client.post("/assistant/stream", json={"message": "你好"})
        assert response.status_code == 403
        assert "starter assistant limit" in response.text
    finally:
        app.dependency_overrides.clear()
