import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import User, Subscription, Organization
from app.auth.service import _hash_password, update_subscription_command

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
    db.commit()
    sub = Subscription(user_id=user.id, plan=plan, status="active")
    db.add(sub)
    db.commit()
    return user


def test_upgrade_starter_to_professional(db: Session):
    user = _make_user(db, "a@b.com", "starter")
    result = update_subscription_command(db, user.id, "professional")
    assert result.plan == "professional"
    assert result.status == "active"


def test_downgrade_professional_to_starter(db: Session):
    user = _make_user(db, "b@c.com", "professional")
    result = update_subscription_command(db, user.id, "starter")
    assert result.plan == "starter"


def test_upgrade_creates_subscription_if_missing(db: Session):
    user = User(email="c@d.com", display_name="C", password_hash=_hash_password("pass"), role="member", org_id=ORG_ID)
    db.add(user)
    db.commit()
    # No subscription row
    result = update_subscription_command(db, user.id, "professional")
    assert result.plan == "professional"
    assert result.status == "active"


def test_invalid_plan_raises(db: Session):
    user = _make_user(db, "d@e.com", "starter")
    with pytest.raises(ValueError, match="Invalid plan"):
        update_subscription_command(db, user.id, "mega")
