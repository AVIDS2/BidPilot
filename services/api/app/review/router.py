from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import require_auth
from app.db import get_db

from .schemas import ReviewCommentCreate, ReviewCommentRead, ReviewDecisionCreate, ReviewDecisionRead, ReviewThreadRead
from .service import add_comment_command, list_comments_query, list_threads_query, submit_review_decision_command

router = APIRouter(prefix="/review", tags=["review"])


@router.post("/decisions", response_model=ReviewDecisionRead, status_code=status.HTTP_201_CREATED)
def submit_review_decision(
    payload: ReviewDecisionCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> ReviewDecisionRead:
    return submit_review_decision_command(db, payload, current_user)


@router.get("/threads", response_model=list[ReviewThreadRead])
def list_threads(
    section_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> list[ReviewThreadRead]:
    return list_threads_query(db, section_id, current_user)


@router.post("/comments", response_model=ReviewCommentRead, status_code=status.HTTP_201_CREATED)
def add_comment(
    payload: ReviewCommentCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> ReviewCommentRead:
    return add_comment_command(db, payload, current_user)


@router.get("/threads/{thread_id}/comments", response_model=list[ReviewCommentRead])
def list_comments(
    thread_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_auth),
) -> list[ReviewCommentRead]:
    return list_comments_query(db, thread_id, current_user)
