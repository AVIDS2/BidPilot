from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.auth.service import _hash_password
from app.models import Organization, OrganizationMembership, Project, Subscription, User, UsageEvent
from app.usage.schemas import ProviderSource
from app.usage.service import count_official_workflow_starts, get_usage_quota, record_usage_event


ORG_ID = "00000000-0000-0000-0000-000000000001"


def _make_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(Organization(id=ORG_ID, slug="default", name="Default Organization"))
    session.commit()
    return session


def _make_user(db: Session, plan: str) -> tuple[User, Project]:
    org = Organization(slug=f"quota-{plan}", name=f"Quota {plan}")
    db.add(org)
    db.flush()
    user = User(
        email=f"quota-{plan}@example.com",
        display_name="Quota User",
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
        slug=f"quota-{plan}-project",
        name="Quota Project",
        scenario_package="bidpilot",
    )
    db.add(project)
    db.commit()
    db.refresh(user)
    db.refresh(project)
    return user, project


def test_monthly_quota_counts_current_month_only():
    db = _make_db()
    try:
        user, project = _make_user(db, "starter")
        record_usage_event(
            db,
            user_id=user.id,
            org_id=user.org_id,
            project_id=project.id,
            event_type="workflow_draft_started",
            provider_source=ProviderSource.OFFICIAL,
        )
        db.commit()

        quota = get_usage_quota(db, user.id)
        assert quota.plan == "starter"
        assert quota.monthly_workflow_limit == 3
        assert quota.monthly_workflow_used == 1
        assert quota.monthly_workflow_remaining == 2
        assert quota.monthly_assistant_limit == 100
        assert quota.monthly_assistant_used == 0
        assert quota.monthly_assistant_remaining == 100
        assert quota.monthly_indexing_limit == 5
        assert quota.monthly_indexing_used == 0
        assert quota.monthly_indexing_remaining == 5
        assert quota.trial_window_start.startswith(datetime.now(UTC).strftime("%Y-%m-01"))
    finally:
        db.close()


def test_monthly_quota_unlimited_for_professional():
    db = _make_db()
    try:
        user, project = _make_user(db, "professional")
        for _ in range(4):
            record_usage_event(
                db,
                user_id=user.id,
                org_id=user.org_id,
                project_id=project.id,
                event_type="workflow_draft_started",
                provider_source=ProviderSource.OFFICIAL,
            )
        db.commit()

        quota = get_usage_quota(db, user.id)
        assert quota.plan == "professional"
        assert quota.monthly_workflow_limit == -1
        assert quota.monthly_workflow_used == 4
        assert quota.monthly_workflow_remaining is None
        assert quota.monthly_assistant_limit == -1
        assert quota.monthly_assistant_remaining is None
        assert quota.monthly_indexing_limit == -1
        assert quota.monthly_indexing_remaining is None
    finally:
        db.close()


def test_count_official_workflow_starts_ignores_byok():
    db = _make_db()
    try:
        user, project = _make_user(db, "starter")
        for _ in range(2):
            record_usage_event(
                db,
                user_id=user.id,
                org_id=user.org_id,
                project_id=project.id,
                event_type="workflow_draft_started",
                provider_source=ProviderSource.BYOK,
            )
        db.commit()

        assert count_official_workflow_starts(db, user.org_id) == 0
        assert db.query(UsageEvent).count() == 2
    finally:
        db.close()
