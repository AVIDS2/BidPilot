
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


def test_create_demo_project_is_idempotent_and_traceable(client) -> None:
    first = client.post("/projects/demo")
    assert first.status_code == 201
    project = first.json()
    assert project["name"].startswith("演示 ·")

    second = client.post("/projects/demo")
    assert second.status_code == 200
    assert second.json()["id"] == project["id"]

    bundles = client.get(f"/bundles?project_id={project['id']}")
    assert bundles.status_code == 200
    assert len(bundles.json()) == 1
    assert bundles.json()[0]["source_type"] == "builtin_demo"
    assert bundles.json()[0]["ingest_status"] == "ingested"

    documents = client.get(f"/documents?bundle_id={bundles.json()[0]['id']}")
    assert documents.status_code == 200
    assert documents.json()["total"] == 3
    document = documents.json()["items"][0]
    download = client.get(f"/documents/{document['id']}/download")
    assert download.status_code == 200
    assert b"\xe6" in download.content

    requirements = client.get(f"/requirements?project_id={project['id']}")
    assert requirements.status_code == 200
    assert len(requirements.json()) == 6
    assert all(item["source_document_id"] for item in requirements.json())

    evidence = client.get(f"/evidence?project_id={project['id']}")
    assert evidence.status_code == 200
    assert len(evidence.json()) == 4

    events = client.get(f"/audit/events?project_id={project['id']}")
    assert events.status_code == 200
    seeded = next(event for event in events.json() if event["event_type"] == "project.demo_seeded")
    assert seeded["payload"]["source_kind"] == "builtin_demo"
