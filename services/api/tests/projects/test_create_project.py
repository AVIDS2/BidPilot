import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.schemas import CurrentUser
from app.auth.service import _hash_password
from app.db import Base, get_db
from app.main import app
from app.models import Organization, User


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with SessionLocal() as db:
        org = Organization(
            id="00000000-0000-0000-0000-000000000001",
            slug="default",
            name="Default Organization",
        )
        user = User(
            id="dev-user",
            email="dev@docpilot.local",
            display_name="Dev User",
            password_hash=_hash_password("Test1234"),
            role="admin",
            email_verified=True,
            org_id=org.id,
        )
        db.add_all([org, user])
        db.commit()

    async def override_require_auth():
        return CurrentUser(
            id="dev-user",
            email="dev@docpilot.local",
            display_name="Dev User",
            role="admin",
            plan="professional",
            email_verified=True,
            disabled=False,
            org_id="00000000-0000-0000-0000-000000000001",
            org_slug="default",
        )

    def override_get_db():
        with SessionLocal() as db:
            yield db

    from app.auth.service import require_auth

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_auth] = override_require_auth
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_create_project(client) -> None:
    response = client.post(
        "/projects",
        json={"name": "Acme Bid", "scenario_package": "bidpilot"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Acme Bid"
    assert data["scenario_package"] == "bidpilot"
