import uuid

from app.db import SessionLocal
from app.models import Bundle, ExecutionRun, Project
from app.tasks import ping, ingest_bundle, draft_section


def _unique_suffix() -> str:
    return uuid.uuid4().hex[:8]


def test_ping_task() -> None:
    assert ping() == "pong"


def test_ingest_bundle_task() -> None:
    db = SessionLocal()
    try:
        s = _unique_suffix()
        project = Project(name=f"Ingest Test {s}", slug=f"ingest-test-{s}", scenario_package="bidpilot")
        db.add(project)
        db.commit()
        db.refresh(project)

        bundle = Bundle(project_id=project.id, label="Test Bundle", source_type="upload")
        db.add(bundle)
        db.commit()
        db.refresh(bundle)
        bundle_id = bundle.id
    finally:
        db.close()

    result = ingest_bundle(bundle_id)
    assert result["bundle_id"] == bundle_id
    assert result["status"] == "ingested"

    # Verify DB state
    db = SessionLocal()
    try:
        b = db.get(Bundle, bundle_id)
        assert b is not None
        assert b.ingest_status == "ingested"
    finally:
        db.close()


def test_draft_section_task() -> None:
    db = SessionLocal()
    try:
        s = _unique_suffix()
        project = Project(name=f"Draft Test {s}", slug=f"draft-test-{s}", scenario_package="bidpilot")
        db.add(project)
        db.commit()
        db.refresh(project)

        run = ExecutionRun(project_id=project.id, run_type="draft_section")
        db.add(run)
        db.commit()
        db.refresh(run)
        run_id = run.id
        project_id = project.id
    finally:
        db.close()

    result = draft_section(run_id, project_id, "technical-approach")
    assert result["run_id"] == run_id
    assert result["status"] == "succeeded"

    # Verify DB state
    db = SessionLocal()
    try:
        r = db.get(ExecutionRun, run_id)
        assert r is not None
        assert r.status == "succeeded"
        assert r.finished_at is not None
    finally:
        db.close()
