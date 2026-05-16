from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import record_audit_event
from app.email.service import send_review_notification_email
from app.models import Deliverable, DeliverableSection, Project, ReviewComment, ReviewThread

from .repository import create_comment, create_review_thread, list_comments_by_thread, list_threads_by_section
from .schemas import ReviewCommentCreate, ReviewCommentRead, ReviewDecisionCreate, ReviewDecisionRead, ReviewThreadRead


def submit_review_decision_command(db: Session, payload: ReviewDecisionCreate) -> ReviewDecisionRead:
    # Update section status based on decision
    section = db.get(DeliverableSection, payload.section_id)
    if section is None:
        raise ValueError("Section not found")

    section.status = payload.decision  # "approved" or "rejected"
    db.flush()

    # Create or update review thread
    thread = ReviewThread(
        deliverable_section_id=payload.section_id,
        status=payload.decision,
        opened_by="dev-user",
        resolved_by="dev-user",
    )
    thread = create_review_thread(db, thread)

    # Add decision as a comment if comment provided
    if payload.comment:
        comment = ReviewComment(
            review_thread_id=thread.id,
            author_type="human",
            author_id="dev-user",
            body=payload.comment,
        )
        db.add(comment)

    # Resolve project_id for audit
    project_id = ""
    deliverable = db.get(Deliverable, section.deliverable_id)
    if deliverable:
        project_id = deliverable.project_id

    if project_id:
        record_audit_event(db, project_id=project_id, event_type=f"review.{payload.decision}", payload={"section_id": payload.section_id, "section_key": section.section_key, "comment": payload.comment})

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
                record_audit_event(db, project_id=project_id, event_type="deliverable.approved", payload={"deliverable_id": deliverable.id})

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


def list_threads_query(db: Session, section_id: str) -> list[ReviewThreadRead]:
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


def add_comment_command(db: Session, payload: ReviewCommentCreate) -> ReviewCommentRead:
    comment = ReviewComment(
        review_thread_id=payload.thread_id,
        author_type=payload.author_type,
        author_id=payload.author_id,
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


def list_comments_query(db: Session, thread_id: str) -> list[ReviewCommentRead]:
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
