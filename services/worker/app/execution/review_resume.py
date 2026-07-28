"""Resolve a LangGraph resume from the durable review decision.

Celery delivers messages at least once. The queue argument is only a delivery
hint; the final approval/rejection lives in PostgreSQL on the immutable
``SectionVersion`` and its ``ReviewThread``. Re-reading that relation before a
``Command(resume=...)`` prevents a delayed or replayed broker message from
changing the business decision used by the graph.
"""

from __future__ import annotations

from sqlalchemy import select

from app.db import SessionLocal
from contracts.models import ExecutionRun, ReviewComment, ReviewThread, SectionVersion


class DurableReviewResumeError(RuntimeError):
    """Raised when a checkpoint resume no longer matches its review record."""


def resolve_durable_review_resume(
    *,
    run_id: str,
    requested_decision: str,
    requested_feedback: str | None,
) -> tuple[str, str | None]:
    """Return the graph decision backed by the committed human review.

    Older or non-review interruptions do not carry ``review_resume`` metadata,
    so they retain the explicitly supplied resume payload. New review-driven
    resumes must validate the version, thread, and final decision together.
    """
    db = SessionLocal()
    try:
        run = db.get(ExecutionRun, run_id)
        if run is None:
            raise DurableReviewResumeError("execution_run_not_found")

        input_json = run.input_json if isinstance(run.input_json, dict) else {}
        reference = input_json.get("review_resume")
        if not isinstance(reference, dict):
            _validate_graph_resume_payload(requested_decision, requested_feedback)
            return requested_decision, requested_feedback

        review_thread_id = reference.get("review_thread_id")
        section_version_id = reference.get("section_version_id")
        if not isinstance(review_thread_id, str) or not isinstance(section_version_id, str):
            raise DurableReviewResumeError("review_resume_reference_invalid")

        version = db.get(SectionVersion, section_version_id)
        thread = db.get(ReviewThread, review_thread_id)
        if version is None or version.generation_run_id != run.id:
            raise DurableReviewResumeError("review_resume_version_mismatch")
        if thread is None or thread.section_version_id != version.id:
            raise DurableReviewResumeError("review_resume_thread_mismatch")

        if thread.status == "approved":
            return "approved", None
        if thread.status != "rejected":
            raise DurableReviewResumeError("review_resume_not_finalized")

        feedback = db.scalar(
            select(ReviewComment.body)
            .where(
                ReviewComment.review_thread_id == thread.id,
                ReviewComment.author_type == "human",
            )
            .order_by(ReviewComment.created_at.desc(), ReviewComment.id.desc())
            .limit(1)
        )
        return "rejected_with_feedback", feedback if isinstance(feedback, str) else None
    finally:
        db.close()


def _validate_graph_resume_payload(decision: str, feedback: str | None) -> None:
    if decision not in {"approved", "rejected_with_feedback"}:
        raise DurableReviewResumeError("unsupported_resume_decision")
    if feedback is not None and not isinstance(feedback, str):
        raise DurableReviewResumeError("resume_feedback_invalid")
