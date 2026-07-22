import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Organization, OrganizationMembership, Project, Subscription, User
from app.auth.service import _hash_password, check_plan_limit, PLAN_LIMITS

ORG_ID = "00000000-0000-0000-0000-000000000001"


def _seed_org(db: Session) -> None:
    db.add(Organization(id=ORG_ID, slug="default", name="Default Organization"))
    db.commit()


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        _seed_org(session)
        yield session


def _make_user(db: Session, email: str, plan: str = "starter") -> User:
    user = User(email=email, display_name=email.split("@")[0], password_hash=_hash_password("pass"), role="member", org_id=ORG_ID)
    db.add(user)
    db.flush()
    db.add(OrganizationMembership(org_id=ORG_ID, user_id=user.id, role="owner"))
    db.commit()
    sub = Subscription(user_id=user.id, plan=plan, status="active")
    db.add(sub)
    db.commit()
    return user


def test_plan_limits_constants():
    assert PLAN_LIMITS["starter"] == 3
    assert PLAN_LIMITS["professional"] == -1
    assert PLAN_LIMITS["enterprise"] == -1


def test_starter_under_limit(db: Session):
    user = _make_user(db, "a@b.com", "starter")
    for i in range(3):
        db.add(Project(slug=f"p{i}", name=f"P{i}", scenario_package="bidpilot", status="active", org_id=ORG_ID))
    db.commit()
    # Should not raise — exactly at limit is still allowed
    check_plan_limit(db, user.id, "projects")


def test_starter_over_limit(db: Session):
    user = _make_user(db, "b@c.com", "starter")
    for i in range(3):
        db.add(Project(slug=f"p{i}", name=f"P{i}", scenario_package="bidpilot", status="active", org_id=ORG_ID))
    db.commit()
    # 4th project should fail
    with pytest.raises(ValueError, match="plan limit"):
        check_plan_limit(db, user.id, "projects", delta=1)


def test_professional_unlimited(db: Session):
    user = _make_user(db, "c@d.com", "professional")
    for i in range(10):
        db.add(Project(slug=f"p{i}", name=f"P{i}", scenario_package="bidpilot", status="active", org_id=ORG_ID))
    db.commit()
    # Should never raise
    check_plan_limit(db, user.id, "projects", delta=1)


def test_no_subscription_defaults_to_starter(db: Session):
    user = User(email="d@e.com", display_name="D", password_hash=_hash_password("pass"), role="member", org_id=ORG_ID)
    db.add(user)
    db.flush()
    db.add(OrganizationMembership(org_id=ORG_ID, user_id=user.id, role="owner"))
    db.commit()
    # No subscription record → treated as starter
    with pytest.raises(ValueError, match="plan limit"):
        for i in range(4):
            db.add(Project(slug=f"p{i}", name=f"P{i}", scenario_package="bidpilot", status="active", org_id=ORG_ID))
        db.commit()
        check_plan_limit(db, user.id, "projects", delta=1)
