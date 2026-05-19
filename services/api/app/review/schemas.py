from pydantic import BaseModel


class ReviewDecisionCreate(BaseModel):
    section_id: str
    decision: str
    comment: str | None = None


class ReviewDecisionRead(BaseModel):
    id: str
    section_id: str
    decision: str
    comment: str | None = None


class ReviewThreadRead(BaseModel):
    id: str
    deliverable_section_id: str
    status: str
    opened_by: str
    resolved_by: str | None = None


class ReviewCommentCreate(BaseModel):
    thread_id: str
    body: str
    author_type: str = "human"
    author_id: str = "dev-user"


class ReviewCommentRead(BaseModel):
    id: str
    review_thread_id: str
    author_type: str
    author_id: str
    body: str
    created_at: str
