from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.auth.service import _hash_password
from app.models import Organization, OrganizationMembership, Project, Subscription, User, UsageEvent
from app.usage.schemas import ProviderSource
from app.usage.service import (
    ASSISTANT_MESSAGE_STARTED,
    EMBEDDING_INDEX_STARTED,
    UsageLimitExceeded,
    check_assistant_quota,
    check_indexing_quota,
    check_workflow_quota,
    current_period_key,
    record_usage_event,
)


def _make_user_project(db: Session, plan: str = "starter"):
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
    db.add(OrganizationMembership(org_id=org.id, user_id=user.id, role="owner"))
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


def _make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    session.add(Organization(id="00000000-0000-0000-0000-000000000001", slug="default", name="Default Organization"))
    session.commit()
    return session


def test_starter_official_workflow_quota_allows_first_three():
    db = _make_db()
    try:
        user, project = _make_user_project(db, "starter")

        for _ in range(3):
            check_workflow_quota(db, user.id, user.org_id, ProviderSource.OFFICIAL)
            record_usage_event(
                db,
                user_id=user.id,
                org_id=user.org_id,
                project_id=project.id,
                event_type="workflow_draft_started",
                provider_source=ProviderSource.OFFICIAL,
            )
        db.commit()
    finally:
        db.close()


def test_starter_official_workflow_quota_blocks_fourth():
    db = _make_db()
    try:
        user, project = _make_user_project(db, "starter")

        for _ in range(3):
            record_usage_event(
                db,
                user_id=user.id,
                org_id=user.org_id,
                project_id=project.id,
                event_type="workflow_draft_started",
                provider_source=ProviderSource.OFFICIAL,
            )
        db.commit()

        try:
            check_workflow_quota(db, user.id, user.org_id, ProviderSource.OFFICIAL)
        except UsageLimitExceeded as exc:
            assert "starter workflow trial limit" in str(exc)
        else:
            raise AssertionError("Expected UsageLimitExceeded")
    finally:
        db.close()


def test_professional_bypasses_starter_workflow_quota():
    db = _make_db()
    try:
        user, project = _make_user_project(db, "professional")

        for _ in range(5):
            record_usage_event(
                db,
                user_id=user.id,
                org_id=user.org_id,
                project_id=project.id,
                event_type="workflow_draft_started",
                provider_source=ProviderSource.OFFICIAL,
            )
        db.commit()

        check_workflow_quota(db, user.id, user.org_id, ProviderSource.OFFICIAL)
    finally:
        db.close()


def test_byok_does_not_consume_official_workflow_quota():
    db = _make_db()
    try:
        user, project = _make_user_project(db, "starter")

        for _ in range(5):
            record_usage_event(
                db,
                user_id=user.id,
                org_id=user.org_id,
                project_id=project.id,
                event_type="workflow_draft_started",
                provider_source=ProviderSource.BYOK,
            )
        db.commit()

        check_workflow_quota(db, user.id, user.org_id, ProviderSource.OFFICIAL)
    finally:
        db.close()


def test_starter_official_assistant_quota_blocks_after_limit():
    db = _make_db()
    try:
        user, project = _make_user_project(db, "starter")

        for _ in range(100):
            record_usage_event(
                db,
                user_id=user.id,
                org_id=user.org_id,
                project_id=project.id,
                event_type=ASSISTANT_MESSAGE_STARTED,
                provider_source=ProviderSource.OFFICIAL,
            )
        db.commit()

        try:
            check_assistant_quota(db, user.id, user.org_id, ProviderSource.OFFICIAL)
        except UsageLimitExceeded as exc:
            assert "starter assistant limit" in str(exc)
        else:
            raise AssertionError("Expected UsageLimitExceeded")
    finally:
        db.close()


def test_byok_assistant_does_not_consume_official_assistant_quota():
    db = _make_db()
    try:
        user, project = _make_user_project(db, "starter")

        for _ in range(120):
            record_usage_event(
                db,
                user_id=user.id,
                org_id=user.org_id,
                project_id=project.id,
                event_type=ASSISTANT_MESSAGE_STARTED,
                provider_source=ProviderSource.BYOK,
            )
        db.commit()

        check_assistant_quota(db, user.id, user.org_id, ProviderSource.OFFICIAL)
    finally:
        db.close()


def test_starter_official_indexing_quota_blocks_after_limit():
    db = _make_db()
    try:
        user, project = _make_user_project(db, "starter")

        for _ in range(5):
            record_usage_event(
                db,
                user_id=user.id,
                org_id=user.org_id,
                project_id=project.id,
                event_type=EMBEDDING_INDEX_STARTED,
                provider_source=ProviderSource.OFFICIAL,
            )
        db.commit()

        try:
            check_indexing_quota(db, user.id, user.org_id, ProviderSource.OFFICIAL)
        except UsageLimitExceeded as exc:
            assert "starter indexing limit" in str(exc)
        else:
            raise AssertionError("Expected UsageLimitExceeded")
    finally:
        db.close()


def test_record_usage_event_persists():
    db = _make_db()
    try:
        user, project = _make_user_project(db, "starter")

        event = record_usage_event(
            db,
            user_id=user.id,
            org_id=user.org_id,
            project_id=project.id,
            event_type="workflow_draft_started",
            provider_source=ProviderSource.OFFICIAL,
            metadata_json={"source": "test"},
        )
        db.commit()

        loaded = db.query(UsageEvent).filter_by(id=event.id).first()
        assert loaded is not None
        assert loaded.provider_source == ProviderSource.OFFICIAL.value
        assert loaded.metadata_json == {"source": "test"}
        assert loaded.period_key == current_period_key()
    finally:
        db.close()
