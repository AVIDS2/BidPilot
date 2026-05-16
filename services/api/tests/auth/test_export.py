"""Test user data export returns all entity types."""
import uuid

from app.auth.service import register_user_command, login_command
from app.auth.schemas import UserRegister
from app.models import Project, Bundle, SourceDocument, Deliverable, DeliverableSection
from app.models import RequirementItem, Evidence, ExecutionRun, ReviewComment, ReviewThread, SectionVersion, User, AuditEvent


def _unique_id() -> str:
    return uuid.uuid4().hex[:8]


def test_export_includes_all_entity_types(test_db, client):
    suffix = _unique_id()
    email = f"export-test-{suffix}@docpilot.ai"
    payload = UserRegister(email=email, display_name="Export Test", password="Test1234")
    register_user_command(test_db, payload)
    u = test_db.query(User).filter_by(email=email).first()
    u.email_verified = True
    test_db.commit()
    token = login_command(test_db, email, "Test1234").access_token

    # Create entities in FK dependency order with flush after each
    pid = f"exp-p-{suffix}"
    bid = f"exp-b-{suffix}"
    sd_id = f"exp-sd-{suffix}"
    did = f"exp-d-{suffix}"
    sid = f"exp-s-{suffix}"
    rid = f"exp-r-{suffix}"
    eid = f"exp-ev-{suffix}"
    run_id = f"exp-run-{suffix}"
    rt_id = f"exp-rt-{suffix}"
    rc_id = f"exp-rc-{suffix}"
    sv_id = f"exp-sv-{suffix}"

    p = Project(id=pid, slug=f"export-proj-{suffix}", name="Export Project", scenario_package="bidpilot")
    test_db.add(p)
    test_db.flush()

    b = Bundle(id=bid, project_id=pid, label="Test Bundle", source_type="upload")
    test_db.add(b)
    test_db.flush()

    sd = SourceDocument(id=sd_id, bundle_id=bid, storage_key="test.txt", mime_type="text/plain", checksum="abc123", original_filename="test.txt")
    test_db.add(sd)
    test_db.flush()

    d = Deliverable(id=did, project_id=pid, type="proposal", title="Test Del")
    test_db.add(d)
    test_db.flush()

    s = DeliverableSection(id=sid, deliverable_id=did, section_key="intro", title="Intro")
    test_db.add(s)
    test_db.flush()

    r = RequirementItem(id=rid, project_id=pid, section_key="intro", requirement_text="Must have X")
    test_db.add(r)
    test_db.flush()

    e = Evidence(id=eid, project_id=pid, quote_text="Evidence text")
    test_db.add(e)
    test_db.flush()

    run = ExecutionRun(id=run_id, project_id=pid, run_type="draft")
    test_db.add(run)
    test_db.flush()

    rt = ReviewThread(id=rt_id, deliverable_section_id=sid, opened_by=u.id)
    test_db.add(rt)
    test_db.flush()

    rc = ReviewComment(id=rc_id, review_thread_id=rt_id, author_type="human", author_id=u.id, body="Comment")
    test_db.add(rc)
    test_db.flush()

    sv = SectionVersion(id=sv_id, deliverable_section_id=sid, version_number=1, content_markdown="# Draft")
    test_db.add(sv)
    test_db.flush()

    # Create audit events to link user to the project
    ae = AuditEvent(id=f"exp-ae-{suffix}", project_id=pid, actor_type="human", actor_id=u.id, event_type="export.test")
    test_db.add(ae)
    test_db.flush()

    test_db.commit()

    resp = client.get("/auth/me/export", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "account" in data
    assert "deliverables" in data
    assert "sections" in data
    assert "requirements" in data
    assert "evidence" in data
    assert "execution_runs" in data
    assert "review_comments" in data
    assert "documents" in data
    assert "bundles" in data
