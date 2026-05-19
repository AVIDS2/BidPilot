"""End-to-end smoke test covering full MVP acceptance criteria.

Covers: project → bundle → document upload → deliverable → section →
requirement → draft → evidence → review → redraft → export → audit trail.
"""

from fastapi.testclient import TestClient

from app.main import app


def test_full_e2e_flow() -> None:
    client = TestClient(app)

    # 1. Create project
    proj = client.post("/projects", json={"name": "E2E Smoke Test", "scenario_package": "bidpilot"})
    assert proj.status_code == 201
    project_id = proj.json()["id"]

    # 2. Register bundle
    bundle = client.post("/bundles", json={"project_id": project_id, "label": "RFP Pack", "source_type": "upload"})
    assert bundle.status_code == 201
    bundle_id = bundle.json()["id"]
    assert bundle.json()["ingest_status"] == "queued"

    # 3. Upload a document to the bundle
    doc = client.post(
        "/documents/upload",
        params={"bundle_id": bundle_id},
        files={"file": ("rfp.txt", b"The system shall provide SSO authentication.\nThe system shall support role-based access control.", "text/plain")},
    )
    assert doc.status_code == 201

    # 4. Create deliverable
    dlv = client.post("/deliverables", json={"project_id": project_id, "type": "proposal", "title": "Technical Proposal"})
    assert dlv.status_code == 201
    deliverable_id = dlv.json()["id"]
    assert dlv.json()["export_status"] == "not_exported"

    # 5. Create deliverable section
    sec = client.post(
        "/deliverables/sections",
        json={"deliverable_id": deliverable_id, "section_key": "exec-summary", "title": "Executive Summary"},
    )
    assert sec.status_code == 201
    section_id = sec.json()["id"]

    # 6. Create a requirement manually
    req = client.post("/requirements", json={"project_id": project_id, "section_key": "exec-summary", "requirement_text": "System shall authenticate via SSO", "priority": "high"})
    assert req.status_code == 201
    req_id = req.json()["id"]

    # 7. Update requirement (manual correction)
    updated_req = client.put(f"/requirements/{req_id}", json={"status": "confirmed"})
    assert updated_req.status_code == 200
    assert updated_req.json()["status"] == "confirmed"

    # 8. Request draft
    draft = client.post("/drafting/sections", json={"project_id": project_id, "section_key": "exec-summary"})
    assert draft.status_code == 202
    run_id = draft.json()["run_id"]

    # 9. Request redraft with review feedback
    redraft = client.post("/drafting/sections/redraft", json={"project_id": project_id, "section_key": "exec-summary", "review_feedback": "Add more detail on SSO integration"})
    assert redraft.status_code == 202

    # 10. Check execution runs
    runs = client.get(f"/execution/runs?project_id={project_id}")
    assert runs.status_code == 200
    assert any(r["id"] == run_id for r in runs.json())

    # 11. Check evidence exists
    evidence = client.get(f"/evidence?project_id={project_id}")
    assert evidence.status_code == 200

    # 12. Submit review decision
    decision = client.post("/review/decisions", json={"section_id": section_id, "decision": "approved"})
    assert decision.status_code == 201

    # 13. Add review comment
    thread_id = decision.json()["id"]
    comment = client.post("/review/comments", json={"thread_id": thread_id, "body": "Looks good!", "author_type": "human", "author_id": "user-1"})
    assert comment.status_code == 201

    # 14. List review comments
    comments = client.get(f"/review/threads/{thread_id}/comments")
    assert comments.status_code == 200
    assert len(comments.json()) >= 1

    # 15. Export deliverable as DOCX
    export = client.get(f"/export/deliverables/{deliverable_id}/docx")
    assert export.status_code == 200
    assert export.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    # 16. Verify export status updated
    deliverables = client.get(f"/deliverables?project_id={project_id}")
    assert deliverables.status_code == 200
    d = next(d for d in deliverables.json() if d["id"] == deliverable_id)
    assert d["export_status"] == "exported"

    # 17. Check audit trail covers key events
    events = client.get(f"/audit/events?project_id={project_id}")
    assert events.status_code == 200
    event_types = [e["event_type"] for e in events.json()]
    assert "bundle.registered" in event_types
    assert "draft.requested" in event_types
    assert "draft.redraft" in event_types
    assert "requirement.updated" in event_types
    assert "deliverable.exported" in event_types

    # 18. List bundles and deliverables
    bundles = client.get(f"/bundles?project_id={project_id}")
    assert bundles.status_code == 200
    assert len(bundles.json()) >= 1

    # 19. Health check
    health = client.get("/health")
    assert health.status_code == 200
