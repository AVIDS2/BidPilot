"""Test review notification emails are triggered on decisions."""
import uuid
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.auth.schemas import CurrentUser
from app.review.schemas import ReviewDecisionCreate
from app.review.service import submit_review_decision_command
from app.models import (
    AuditEvent,
    Deliverable,
    DeliverableSection,
    ExecutionRun,
    Project,
    ReviewComment,
    ReviewThread,
    SectionVersion,
    TaskOutboxEvent,
)


def _unique_id() -> str:
    return uuid.uuid4().hex[:8]


def _admin_user() -> CurrentUser:
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


def test_approve_sends_notification(test_db):
    uid = _unique_id()
    pid = f"p-notify-{uid}"
    did = f"d-notify-{uid}"
    sid = f"s-notify-{uid}"

    p = Project(id=pid, slug=f"nt-{uid}", name="Notify Test", org_id="00000000-0000-0000-0000-000000000001", scenario_package="bidpilot")
    test_db.add(p)
    test_db.flush()
    d = Deliverable(id=did, project_id=pid, type="proposal", title="Test Del")
    test_db.add(d)
    test_db.flush()
    s = DeliverableSection(id=sid, deliverable_id=did, section_key="intro", title="Intro")
    test_db.add(s)
    test_db.flush()
    version = SectionVersion(
        deliverable_section_id=sid,
        version_number=1,
        content_markdown="Approved introduction.",
    )
    test_db.add(version)
    test_db.commit()

    payload = ReviewDecisionCreate(
        section_id=sid,
        section_version_id=version.id,
        decision="approved",
        comment="Looks good",
    )
    with patch("app.review.service.send_review_notification_email") as mock_send:
        result = submit_review_decision_command(test_db, payload, _admin_user())

    assert result.decision == "approved"
    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["action"] == "approved"

    # Cleanup: service commits internally, so tear down the created rows
    # Order: review_comments -> review_threads -> audit_events -> section -> deliverable -> project
    test_db.query(ReviewComment).filter(
        ReviewComment.review_thread_id.in_(
            test_db.query(ReviewThread.id).filter(ReviewThread.deliverable_section_id == sid)
        )
    ).delete(synchronize_session=False)
    test_db.query(ReviewThread).filter(ReviewThread.deliverable_section_id == sid).delete(synchronize_session=False)
    test_db.query(AuditEvent).filter(AuditEvent.project_id == pid).delete(synchronize_session=False)
    test_db.delete(s)
    test_db.delete(d)
    test_db.delete(p)
    test_db.commit()


def test_reject_sends_notification(test_db):
    uid = _unique_id()
    pid = f"p-notify-{uid}"
    did = f"d-notify-{uid}"
    sid = f"s-notify-{uid}"

    p = Project(id=pid, slug=f"nt-{uid}", name="Notify Test 2", org_id="00000000-0000-0000-0000-000000000001", scenario_package="bidpilot")
    test_db.add(p)
    test_db.flush()
    d = Deliverable(id=did, project_id=pid, type="proposal", title="Test Del 2")
    test_db.add(d)
    test_db.flush()
    s = DeliverableSection(id=sid, deliverable_id=did, section_key="intro", title="Intro")
    test_db.add(s)
    test_db.flush()
    version = SectionVersion(
        deliverable_section_id=sid,
        version_number=1,
        content_markdown="Rejected introduction.",
    )
    test_db.add(version)
    test_db.commit()

    payload = ReviewDecisionCreate(
        section_id=sid,
        section_version_id=version.id,
        decision="rejected",
        comment="Needs work",
    )
    with patch("app.review.service.send_review_notification_email") as mock_send:
        submit_review_decision_command(test_db, payload, _admin_user())

    mock_send.assert_called_once()

    # Cleanup
    test_db.query(ReviewComment).filter(
        ReviewComment.review_thread_id.in_(
            test_db.query(ReviewThread.id).filter(ReviewThread.deliverable_section_id == sid)
        )
    ).delete(synchronize_session=False)
    test_db.query(ReviewThread).filter(ReviewThread.deliverable_section_id == sid).delete(synchronize_session=False)
    test_db.query(AuditEvent).filter(AuditEvent.project_id == pid).delete(synchronize_session=False)
    test_db.delete(s)
    test_db.delete(d)
    test_db.delete(p)
    test_db.commit()


def test_workflow_review_reuses_candidate_thread_and_queues_resume(test_db, default_org_id, monkeypatch):
    uid = _unique_id()
    pid = f"p-workflow-review-{uid}"
    did = f"d-workflow-review-{uid}"
    sid = f"s-workflow-review-{uid}"
    run_id = str(uuid.uuid4())

    project = Project(
        id=pid,
        slug=f"workflow-review-{uid}",
        name="Workflow Review Test",
        org_id=default_org_id,
        scenario_package="bidpilot",
    )
    deliverable = Deliverable(id=did, project_id=pid, type="proposal", title="Workflow Proposal")
    section = DeliverableSection(id=sid, deliverable_id=did, section_key="intro", title="Intro")
    run = ExecutionRun(
        id=run_id,
        project_id=pid,
        run_type="draft_section",
        status="awaiting_human",
        input_json={"section_key": "intro"},
    )
    test_db.add(project)
    test_db.flush()
    test_db.add(deliverable)
    test_db.flush()
    test_db.add_all((section, run))
    test_db.flush()
    version = SectionVersion(
        deliverable_section_id=sid,
        version_number=1,
        content_markdown="Candidate draft.",
        generation_run_id=run_id,
        generation_iteration=1,
    )
    test_db.add(version)
    test_db.flush()
    thread = ReviewThread(
        deliverable_section_id=sid,
        section_version_id=version.id,
        status="open",
        opened_by=run_id,
    )
    test_db.add(thread)
    test_db.commit()

    dispatched: list[str] = []
    monkeypatch.setattr(
        "app.review.service.request_task_outbox_dispatch",
        lambda event_id: dispatched.append(event_id) or True,
    )
    monkeypatch.setattr("app.review.service.send_review_notification_email", lambda **_: None)

    result = submit_review_decision_command(
        test_db,
        ReviewDecisionCreate(
            section_id=sid,
            section_version_id=version.id,
            decision="approved",
        ),
        _admin_user(),
    )

    test_db.expire_all()
    assert result.id == thread.id
    assert test_db.query(ReviewThread).filter_by(section_version_id=version.id).count() == 1
    assert test_db.get(ReviewThread, thread.id).status == "approved"
    assert test_db.get(ExecutionRun, run_id).status == "running"
    persisted_run = test_db.get(ExecutionRun, run_id)
    assert persisted_run is not None
    assert persisted_run.input_json["review_resume"] == {
        "sequence": 1,
        "review_thread_id": thread.id,
        "section_version_id": version.id,
    }
    event = test_db.query(TaskOutboxEvent).filter_by(execution_run_id=run_id).one()
    assert event.task_name == "worker.resume_draft"
    assert event.args_json == [run_id, "approved", None]
    assert dispatched == [event.id]

    # A browser retry of the same decision is idempotent: it must not mutate
    # the approved snapshot, emit another audit/comment, or enqueue a second
    # LangGraph resume. A conflicting later decision is rejected outright.
    repeated = submit_review_decision_command(
        test_db,
        ReviewDecisionCreate(
            section_id=sid,
            section_version_id=version.id,
            decision="approved",
        ),
        _admin_user(),
    )
    assert repeated.id == thread.id
    assert test_db.query(TaskOutboxEvent).filter_by(execution_run_id=run_id).count() == 1
    assert dispatched == [event.id]
    with pytest.raises(HTTPException) as conflict:
        submit_review_decision_command(
            test_db,
            ReviewDecisionCreate(
                section_id=sid,
                section_version_id=version.id,
                decision="rejected",
            ),
            _admin_user(),
        )
    assert conflict.value.status_code == 409

    test_db.query(TaskOutboxEvent).filter_by(execution_run_id=run_id).delete(synchronize_session=False)
    test_db.query(ReviewComment).filter(ReviewComment.review_thread_id == thread.id).delete(synchronize_session=False)
    test_db.query(ReviewThread).filter_by(deliverable_section_id=sid).delete(synchronize_session=False)
    test_db.query(AuditEvent).filter_by(project_id=pid).delete(synchronize_session=False)
    test_db.query(SectionVersion).filter_by(deliverable_section_id=sid).delete(synchronize_session=False)
    test_db.delete(run)
    test_db.delete(section)
    test_db.delete(deliverable)
    test_db.delete(project)
    test_db.commit()
