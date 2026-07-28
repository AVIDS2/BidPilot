from typing import Literal

from pydantic import BaseModel, Field


class ReviewDecisionCreate(BaseModel):
    section_id: str
    # Keep the short legacy forms readable while storing one canonical state.
    decision: Literal["approve", "approved", "reject", "rejected", "needs_revision"]
    # A decision must target one immutable candidate. Falling back to the
    # newest version would let a stale review action approve different content.
    section_version_id: str = Field(min_length=1)
    comment: str | None = None


class ReviewDecisionRead(BaseModel):
    id: str
    section_id: str
    section_version_id: str
    decision: Literal["approved", "rejected"]
    comment: str | None = None


class ReviewThreadRead(BaseModel):
    id: str
    deliverable_section_id: str
    section_version_id: str | None = None
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
