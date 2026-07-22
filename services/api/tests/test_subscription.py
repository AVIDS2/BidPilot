import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import User, Subscription, Organization

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


def test_create_subscription(db: Session):
    user = User(email="a@b.com", display_name="A", password_hash="x", role="member", org_id=ORG_ID)
    db.add(user)
    db.commit()

    sub = Subscription(user_id=user.id, plan="professional", status="active")
    db.add(sub)
    db.commit()

    loaded = db.query(Subscription).filter_by(user_id=user.id).one()
    assert loaded.plan == "professional"
    assert loaded.status == "active"
    assert loaded.stripe_customer_id is None


def test_subscription_defaults_to_starter(db: Session):
    user = User(email="b@c.com", display_name="B", password_hash="x", role="member", org_id=ORG_ID)
    db.add(user)
    db.commit()

    sub = Subscription(user_id=user.id)
    db.add(sub)
    db.commit()

    loaded = db.query(Subscription).filter_by(user_id=user.id).one()
    assert loaded.plan == "starter"
    assert loaded.status == "active"


def test_subscription_unique_per_user(db: Session):
    user = User(email="c@d.com", display_name="C", password_hash="x", role="member", org_id=ORG_ID)
    db.add(user)
    db.commit()

    sub1 = Subscription(user_id=user.id, plan="starter")
    db.add(sub1)
    db.commit()

    sub2 = Subscription(user_id=user.id, plan="professional")
    db.add(sub2)
    with pytest.raises(Exception):
        db.commit()
