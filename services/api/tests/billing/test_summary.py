from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.auth.service import _hash_password
from app.models import Base, Organization, Project, Subscription, User
from app.billing.service import get_billing_summary
from app.usage.service import record_usage_event
from app.usage.schemas import ProviderSource


def _make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    session.add(Organization(id="00000000-0000-0000-0000-000000000001", slug="default", name="Default Organization"))
    session.commit()
    return session


def _make_user(db: Session, plan: str = "starter") -> User:
    org = db.query(Organization).filter_by(slug="default").one()
    user = User(
        email=f"{plan}@example.com",
        display_name=plan,
        password_hash=_hash_password("Test1234"),
        role="member",
        email_verified=True,
        org_id=org.id,
    )
    db.add(user)
    db.flush()
    db.add(Subscription(user_id=user.id, plan=plan, status="active"))
    project = Project(org_id=org.id, slug=f"{plan}-project", name="Project", scenario_package="bidpilot")
    db.add(project)
    db.commit()
    return user


def test_get_billing_summary_includes_usage():
    db = _make_db()
    try:
        user = _make_user(db, "starter")
        project = db.query(Project).filter_by(org_id=user.org_id).one()
        record_usage_event(
            db,
            user_id=user.id,
            org_id=user.org_id,
            project_id=project.id,
            event_type="workflow_draft_started",
            provider_source=ProviderSource.OFFICIAL,
        )
        db.commit()

        summary = get_billing_summary(db, user.id)
        assert summary.plan == "starter"
        assert summary.status == "active"
        assert summary.monthly_workflow_used == 1
        assert summary.monthly_workflow_limit == 3
    finally:
        db.close()
