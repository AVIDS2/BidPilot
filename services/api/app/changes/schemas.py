from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ChangeSetStatus = Literal["pending_parse", "analyzed", "accepted", "dismissed"]
ChangeImpactStatus = Literal["open", "acknowledged", "resolved", "dismissed"]


class DocumentChangeSetCreate(BaseModel):
    replacement_document_id: str


class DocumentChangeSetDecision(BaseModel):
    status: Literal["accepted", "dismissed"]


class DocumentChangeImpactUpdate(BaseModel):
    status: ChangeImpactStatus


class DocumentChangeImpactRead(BaseModel):
    id: str
    impact_key: str
    requirement_id: str | None
    deliverable_section_id: str | None
    impact_type: str
    severity: Literal["low", "medium", "high", "critical"]
    status: ChangeImpactStatus
    summary: str
    locator_json: dict | None
    acknowledged_by_user_id: str | None
    acknowledged_at: datetime | None
    resolved_by_user_id: str | None
    resolved_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None


class DocumentChangeSetRead(BaseModel):
    id: str
    project_id: str
    previous_document_id: str
    replacement_document_id: str
    status: ChangeSetStatus
    summary_json: dict
    created_by_user_id: str | None
    reviewed_by_user_id: str | None
    reviewed_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None
    impacts: list[DocumentChangeImpactRead] = Field(default_factory=list)
