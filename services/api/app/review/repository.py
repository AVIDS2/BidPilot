from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ReviewComment, ReviewThread


# Repository functions for ReviewThread and ReviewComment

def create_review_thread(db: Session, thread: ReviewThread) -> ReviewThread:
    db.add(thread)
    db.flush()
    return thread


def list_threads_by_section(db: Session, section_id: str) -> list[ReviewThread]:
    stmt = (
        select(ReviewThread)
        .where(ReviewThread.deliverable_section_id == section_id)
        .order_by(ReviewThread.id.desc())
    )
    return list(db.scalars(stmt).all())


def create_comment(db: Session, comment: ReviewComment) -> ReviewComment:
    db.add(comment)
    db.flush()
    return comment


def list_comments_by_thread(db: Session, thread_id: str) -> list[ReviewComment]:
    stmt = (
        select(ReviewComment)
        .where(ReviewComment.review_thread_id == thread_id)
        .order_by(ReviewComment.created_at.asc())
    )
    return list(db.scalars(stmt).all())
