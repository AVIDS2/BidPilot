from datetime import datetime

from pydantic import BaseModel, Field


class ResponsePlanRead(BaseModel):
    id: str
    project_id: str
    deliverable_id: str
    version_number: int
    status: str
    source_fingerprint: str
    unmapped_requirement_ids: list[str] = Field(default_factory=list)
    created_by_actor: str
    created_at: datetime | None = None


class ResponsePlanRequirementRead(BaseModel):
    id: str
    requirement_id: str
    requirement_lock_version: int
    requirement_text: str
    priority: str
    owner_user_id: str | None = None
    verification_status: str
    assignment_reason: str


class ResponsePlanEvidenceBindingRead(BaseModel):
    id: str
    evidence_set_id: str
    execution_run_id: str
    generation_iteration: int
    evidence_set_status: str
    unmet_requirement_ids: list[str] = Field(default_factory=list)
    degraded_reasons: list[str] = Field(default_factory=list)
    content_plan: dict = Field(default_factory=dict)
    created_at: datetime | None = None


class ResponsePlanSectionRead(BaseModel):
    id: str
    deliverable_section_id: str
    section_key: str
    title: str
    sort_order: int
    status: str
    requirements: list[ResponsePlanRequirementRead] = Field(default_factory=list)
    evidence_bindings: list[ResponsePlanEvidenceBindingRead] = Field(default_factory=list)


class ResponsePlanDetailRead(ResponsePlanRead):
    sections: list[ResponsePlanSectionRead] = Field(default_factory=list)
