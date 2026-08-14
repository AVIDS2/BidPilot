from datetime import datetime

from pydantic import BaseModel, Field


class CollaborationMemberRead(BaseModel):
    user_id: str
    display_name: str
    role: str


class CollaborationRequirementRead(BaseModel):
    requirement_id: str
    section_key: str
    requirement_text: str
    status: str
    priority: str
    verification_status: str
    owner_user_id: str | None
    owner_display_name: str | None
    reviewer_user_id: str | None
    reviewer_display_name: str | None
    due_at: datetime | None
    overdue: bool
    needs_assignment: bool
    risk_level: str | None
    coverage_status: str | None


class CollaborationBoardRead(BaseModel):
    project_id: str
    members: list[CollaborationMemberRead] = Field(default_factory=list)
    requirement_items: list[CollaborationRequirementRead] = Field(default_factory=list)
    unassigned_requirement_count: int
    overdue_requirement_count: int
    review_required_count: int
    open_review_thread_count: int
    active_workflow_count: int
