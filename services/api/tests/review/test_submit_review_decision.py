import uuid

from fastapi.testclient import TestClient

from app.main import app


def _create_section(client: TestClient) -> tuple[str, str]:
    """Create a reviewable section and return its section/version IDs."""
    from app.db import SessionLocal
    from app.models import Deliverable, DeliverableSection, Project, SectionVersion

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
        version = SectionVersion(
            deliverable_section_id=section.id,
            version_number=1,
            content_markdown="Initial technical approach.",
            created_by_actor="ai",
        )
        db.add(version)
        db.commit()
        return section.id, version.id
    finally:
        db.close()


def test_submit_review_decision() -> None:
    client = TestClient(app)
    section_id, section_version_id = _create_section(client)
    missing_target = client.post(
        "/review/decisions",
        json={"section_id": section_id, "decision": "approve"},
    )
    assert missing_target.status_code == 422

    response = client.post(
        "/review/decisions",
        json={
            "section_id": section_id,
            "decision": "approve",
            "section_version_id": section_version_id,
            "comment": "Looks good",
        },
    )
    assert response.status_code == 201
    assert response.json()["decision"] == "approved"
    assert response.json()["section_version_id"] == section_version_id

    from app.db import SessionLocal
    from app.models import DeliverableSection, ReviewThread

    db = SessionLocal()
    try:
        section = db.get(DeliverableSection, section_id)
        assert section is not None
        assert section.status == "approved"
        assert section.approved_version_id == section_version_id
        thread = db.get(ReviewThread, response.json()["id"])
        assert thread is not None
        assert thread.section_version_id == section_version_id
    finally:
        db.close()
