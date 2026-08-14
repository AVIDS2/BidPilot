from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


OpportunityDecision = Literal["go", "no_go", "conditional_go"]
OpportunityStatus = Literal["draft", "ready", "decided", "archived"]


class OpportunityAssessmentUpsert(BaseModel):
    status: OpportunityStatus = "draft"
    scorecard_json: dict = Field(default_factory=dict)
    risk_summary_json: dict = Field(default_factory=dict)
    rationale: str | None = Field(default=None, max_length=20_000)
    lock_version: int | None = Field(default=None, ge=1)


class OpportunityAssessmentDecisionCreate(BaseModel):
    decision: OpportunityDecision
    rationale: str | None = Field(default=None, max_length=20_000)
    scorecard_json: dict | None = None
    risk_summary_json: dict | None = None
    lock_version: int | None = Field(default=None, ge=1)


class OpportunityAssessmentDecisionRead(BaseModel):
    id: str
    sequence: int
    decision: OpportunityDecision
    rationale: str | None
    scorecard_json: dict
    risk_summary_json: dict
    decided_by_user_id: str | None
    created_at: datetime | None


class OpportunityAssessmentRead(BaseModel):
    id: str
    project_id: str
    status: OpportunityStatus
    decision: Literal["pending", "go", "no_go", "conditional_go"]
    scorecard_json: dict
    risk_summary_json: dict
    rationale: str | None
    created_by_user_id: str | None
    decided_by_user_id: str | None
    decided_at: datetime | None
    lock_version: int
    created_at: datetime | None
    updated_at: datetime | None
    decisions: list[OpportunityAssessmentDecisionRead] = Field(default_factory=list)
