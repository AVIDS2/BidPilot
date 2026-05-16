"""Test review notification emails are triggered on decisions."""
import uuid
from unittest.mock import patch

from app.review.schemas import ReviewDecisionCreate
from app.review.service import submit_review_decision_command
from app.models import Project, Deliverable, DeliverableSection, ReviewThread, ReviewComment, AuditEvent


def _unique_id() -> str:
    return uuid.uuid4().hex[:8]


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
    test_db.commit()

    payload = ReviewDecisionCreate(section_id=sid, decision="approved", comment="Looks good")
    with patch("app.review.service.send_review_notification_email") as mock_send:
        result = submit_review_decision_command(test_db, payload)

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
    test_db.commit()

    payload = ReviewDecisionCreate(section_id=sid, decision="rejected", comment="Needs work")
    with patch("app.review.service.send_review_notification_email") as mock_send:
        submit_review_decision_command(test_db, payload)

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
