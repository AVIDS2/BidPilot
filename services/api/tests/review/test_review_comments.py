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

    # Submit a review decision to create a thread
    decision = client.post("/review/decisions", json={"section_id": section_id, "decision": "needs_revision"})
    assert decision.status_code == 201
    thread_id = decision.json()["id"]

    # Add a comment
    comment = client.post("/review/comments", json={"thread_id": thread_id, "body": "Please clarify scope.", "author_type": "human", "author_id": "user-1"})
    assert comment.status_code == 201
    assert comment.json()["body"] == "Please clarify scope."

    # List comments
    comments = client.get(f"/review/threads/{thread_id}/comments")
    assert comments.status_code == 200
    assert len(comments.json()) >= 1
    assert any(c["body"] == "Please clarify scope." for c in comments.json())
