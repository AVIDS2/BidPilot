from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access.service import (
    require_deliverable_section_capability,
    require_review_thread_capability,
)
from app.audit.service import record_audit_event
from app.auth.schemas import CurrentUser
from app.email.service import send_review_notification_email
from app.models import Deliverable, DeliverableSection, Project, ReviewComment, ReviewThread

from .repository import create_comment, create_review_thread, list_comments_by_thread, list_threads_by_section
from .schemas import ReviewCommentCreate, ReviewCommentRead, ReviewDecisionCreate, ReviewDecisionRead, ReviewThreadRead


def submit_review_decision_command(
    db: Session,
    payload: ReviewDecisionCreate,
    current_user: CurrentUser,
) -> ReviewDecisionRead:
    # Update section status based on decision
    section = require_deliverable_section_capability(
        db,
        current_user=current_user,
        section_id=payload.section_id,
        capability="review.write",
    )

    section.status = payload.decision  # "approved" or "rejected"
    db.flush()

    # Create or update review thread
    thread = ReviewThread(
        deliverable_section_id=payload.section_id,
        status=payload.decision,
        opened_by=current_user.id,
        resolved_by=current_user.id,
    )
    thread = create_review_thread(db, thread)

    # Add decision as a comment if comment provided
    if payload.comment:
        comment = ReviewComment(
            review_thread_id=thread.id,
            author_type="human",
            author_id=current_user.id,
            body=payload.comment,
        )
        db.add(comment)

    # Resolve project_id for audit
    project_id = ""
    deliverable = db.get(Deliverable, section.deliverable_id)
    if deliverable:
        project_id = deliverable.project_id

    if project_id:
        record_audit_event(
            db,
            project_id=project_id,
            event_type=f"review.{payload.decision}",
            actor_type="user",
            actor_id=current_user.id,
            payload={
                "section_id": payload.section_id,
                "section_key": section.section_key,
                "comment": payload.comment,
            },
        )

        # Check if all sections are approved → update deliverable status
        if deliverable and payload.decision == "approved":
            all_sections = list(
                db.scalars(
                    select(DeliverableSection)
                    .where(DeliverableSection.deliverable_id == deliverable.id)
                ).all()
            )
            if all(s.status == "approved" for s in all_sections):
                deliverable.status = "approved"
                record_audit_event(
                    db,
                    project_id=project_id,
                    event_type="deliverable.approved",
                    actor_type="user",
                    actor_id=current_user.id,
                    payload={"deliverable_id": deliverable.id},
                )

        db.commit()

    # Send notification email for review decision
    try:
        deliverable = db.get(Deliverable, section.deliverable_id)
        if deliverable:
            project = db.get(Project, deliverable.project_id)
            if project:
                send_review_notification_email(
                    email="admin@docpilot.local",
                    project_name=project.name,
                    section_title=section.title,
                    action=payload.decision,
                )
    except Exception:
        pass

    return ReviewDecisionRead(
        id=thread.id,
        section_id=payload.section_id,
        decision=payload.decision,
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
    require_review_thread_capability(
        db,
        current_user=current_user,
        thread_id=payload.thread_id,
        capability="review.write",
    )
    comment = ReviewComment(
        review_thread_id=payload.thread_id,
        author_type="human",
        author_id=current_user.id,
        body=payload.body,
    )
    comment = create_comment(db, comment)
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
