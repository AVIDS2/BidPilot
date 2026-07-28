from fastapi.testclient import TestClient

from app.main import app


def test_add_and_list_review_comments() -> None:
    client = TestClient(app)
    # Create project + deliverable + section
    proj = client.post("/projects", json={"name": "Review Comment Test", "scenario_package": "bidpilot"})
    assert proj.status_code == 201
    project_id = proj.json()["id"]

    dlv = client.post("/deliverables", json={"project_id": project_id, "type": "proposal", "title": "Test"})
    assert dlv.status_code == 201
    deliverable_id = dlv.json()["id"]

    sec = client.post(
        "/deliverables/sections",
        json={"deliverable_id": deliverable_id, "section_key": "scope", "title": "Scope"},
    )
    assert sec.status_code == 201
    section_id = sec.json()["id"]

    from app.db import SessionLocal
    from app.models import SectionVersion

    db = SessionLocal()
    try:
        version = SectionVersion(
            deliverable_section_id=section_id,
            version_number=1,
            content_markdown="Scope draft.",
            created_by_actor="ai",
        )
        db.add(version)
        db.commit()
        version_id = version.id
    finally:
        db.close()

    # Submit a review decision to create a thread
    decision = client.post(
        "/review/decisions",
        json={
            "section_id": section_id,
            "section_version_id": version_id,
            "decision": "needs_revision",
        },
    )
    assert decision.status_code == 201
    thread_id = decision.json()["id"]

    # Add a comment
    comment = client.post("/review/comments", json={"thread_id": thread_id, "body": "Please clarify scope.", "author_type": "human", "author_id": "user-1"})
    assert comment.status_code == 201
    assert comment.json()["body"] == "Please clarify scope."
    assert comment.json()["author_id"] == "dev-user"

    from app.db import SessionLocal
    from app.models import AuditEvent

    db = SessionLocal()
    try:
        audit = (
            db.query(AuditEvent)
            .filter_by(project_id=project_id, event_type="review.comment_added")
            .one()
        )
        assert audit.actor_id == "dev-user"
        assert audit.payload_json["review_thread_id"] == thread_id
        assert audit.payload_json["comment_id"] == comment.json()["id"]
    finally:
        db.close()

    # List comments
    comments = client.get(f"/review/threads/{thread_id}/comments")
    assert comments.status_code == 200
    assert len(comments.json()) >= 1
    assert any(c["body"] == "Please clarify scope." for c in comments.json())
