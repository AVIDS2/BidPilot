from sqlalchemy.orm import Session

from app.access.service import (
    require_deliverable_section_capability,
    require_review_thread_capability,
)
from app.audit.service import record_audit_event
from app.auth.schemas import CurrentUser
from app.drafting.service import queue_resume_draft_run
from app.email.service import send_review_notification_email
from app.models import (
    Deliverable,
    DeliverableSection,
    ExecutionRun,
    Project,
    ReviewComment,
)
from app.outbox.service import request_task_outbox_dispatch

from .decision_service import (
    apply_review_decision,
    canonical_review_decision,
    resolve_review_version,
)
from .repository import create_comment, list_comments_by_thread, list_threads_by_section
from .schemas import ReviewCommentCreate, ReviewCommentRead, ReviewDecisionCreate, ReviewDecisionRead, ReviewThreadRead


def submit_review_decision_command(
    db: Session,
    payload: ReviewDecisionCreate,
    current_user: CurrentUser,
) -> ReviewDecisionRead:
    section = require_deliverable_section_capability(
        db,
        current_user=current_user,
        section_id=payload.section_id,
        capability="review.write",
    )
    decision = canonical_review_decision(payload.decision)
    version = resolve_review_version(
        db,
        section=section,
        section_version_id=payload.section_version_id,
    )
    thread, deliverable, decision_applied = apply_review_decision(
        db,
        section=section,
        version=version,
        decision=decision,
        current_user=current_user,
        comment=payload.comment,
    )

    # A candidate created by LangGraph resumes through the same durable outbox
    # path after its version-targeted decision is committed.
    outbox_event = None
    if version.generation_run_id:
        run = db.get(ExecutionRun, version.generation_run_id)
        if run is not None and run.status == "awaiting_human":
            outbox_event = queue_resume_draft_run(
                db,
                run=run,
                current_user=current_user,
                decision=decision,
                feedback=payload.comment if decision == "rejected" else None,
                review_thread_id=thread.id,
                section_version_id=version.id,
            )

    db.commit()
    if outbox_event is not None:
        request_task_outbox_dispatch(outbox_event.id)

    # Send notification email for review decision
    if decision_applied:
        try:
            project = db.get(Project, deliverable.project_id)
            if project:
                send_review_notification_email(
                    email="admin@docpilot.local",
                    project_name=project.name,
                    section_title=section.title,
                    action=decision,
                )
        except Exception:
            pass

    return ReviewDecisionRead(
        id=thread.id,
        section_id=payload.section_id,
        section_version_id=version.id,
        decision=decision,
        comment=payload.comment,
    )


def list_threads_query(
    db: Session,
    section_id: str,
    current_user: CurrentUser,
) -> list[ReviewThreadRead]:
    require_deliverable_section_capability(
        db,
        current_user=current_user,
        section_id=section_id,
        capability="project.read",
    )
    threads = list_threads_by_section(db, section_id)
    return [
        ReviewThreadRead(
            id=t.id,
            deliverable_section_id=t.deliverable_section_id,
            section_version_id=t.section_version_id,
            status=t.status,
            opened_by=t.opened_by,
            resolved_by=t.resolved_by,
        )
        for t in threads
    ]


def add_comment_command(
    db: Session,
    payload: ReviewCommentCreate,
    current_user: CurrentUser,
) -> ReviewCommentRead:
    thread = require_review_thread_capability(
        db,
        current_user=current_user,
        thread_id=payload.thread_id,
        capability="review.write",
    )
    section = db.get(DeliverableSection, thread.deliverable_section_id)
    deliverable = db.get(Deliverable, section.deliverable_id) if section is not None else None
    if section is None or deliverable is None:
        raise RuntimeError(f"Review thread {thread.id} has no deliverable section")
    comment = ReviewComment(
        review_thread_id=payload.thread_id,
        author_type="human",
        author_id=current_user.id,
        body=payload.body,
    )
    comment = create_comment(db, comment)
    record_audit_event(
        db,
        project_id=deliverable.project_id,
        event_type="review.comment_added",
        actor_type="user",
        actor_id=current_user.id,
        payload={
            "review_thread_id": thread.id,
            "section_id": section.id,
            "section_version_id": thread.section_version_id,
            "comment_id": comment.id,
        },
    )
    db.commit()
    return ReviewCommentRead(
        id=comment.id,
        review_thread_id=comment.review_thread_id,
        author_type=comment.author_type,
        author_id=comment.author_id,
        body=comment.body,
        created_at=comment.created_at.isoformat() if comment.created_at else "",
    )


def list_comments_query(
    db: Session,
    thread_id: str,
    current_user: CurrentUser,
) -> list[ReviewCommentRead]:
    require_review_thread_capability(
        db,
        current_user=current_user,
        thread_id=thread_id,
        capability="project.read",
    )
    comments = list_comments_by_thread(db, thread_id)
    return [
        ReviewCommentRead(
            id=c.id,
            review_thread_id=c.review_thread_id,
            author_type=c.author_type,
            author_id=c.author_id,
            body=c.body,
            created_at=c.created_at.isoformat() if c.created_at else "",
        )
        for c in comments
    ]
