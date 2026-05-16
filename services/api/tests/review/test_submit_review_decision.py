import uuid

from fastapi.testclient import TestClient

from app.main import app


def _create_section(client: TestClient) -> str:
    """Create a project → deliverable → section chain and return the section ID."""
    from app.db import SessionLocal
    from app.models import Deliverable, DeliverableSection, Project

    db = SessionLocal()
    try:
        unique = uuid.uuid4().hex[:8]
        project = Project(name=f"Review Test {unique}", slug=f"review-test-{unique}", scenario_package="bidpilot", org_id="00000000-0000-0000-0000-000000000001")
        db.add(project)
        db.commit()
        db.refresh(project)

        deliverable = Deliverable(project_id=project.id, type="proposal", title="Test Proposal")
        db.add(deliverable)
        db.commit()
        db.refresh(deliverable)

        section = DeliverableSection(deliverable_id=deliverable.id, section_key="technical-approach", title="Technical Approach")
        db.add(section)
        db.commit()
        db.refresh(section)
        return section.id
    finally:
        db.close()


def test_submit_review_decision() -> None:
    client = TestClient(app)
    section_id = _create_section(client)
    response = client.post(
        "/review/decisions",
        json={
            "section_id": section_id,
            "decision": "approve",
            "comment": "Looks good",
        },
    )
    assert response.status_code == 201
    assert response.json()["decision"] == "approve"
