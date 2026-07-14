from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReadinessRequirementRead(BaseModel):
    id: str
    section_key: str
    requirement_text: str
    bid_category: str
    is_mandatory: bool
    score_weight: float | None
    risk_level: str
    coverage_status: str
    evidence_status: str
    verification_status: str
    owner_user_id: str | None
    reviewer_user_id: str | None
    due_at: datetime | None
    source_locator_json: dict | None


class ReadinessCounts(BaseModel):
    total: int
    mandatory: int
    scored: int
    covered: int
    partial: int
    uncovered: int
    disputed: int
    not_applicable: int
    accepted_risk: int
    verified: int
    assigned: int


class ReadinessScores(BaseModel):
    mandatory_closure: float = Field(ge=0, le=1)
    scored_coverage: float = Field(ge=0, le=1)
    verification: float = Field(ge=0, le=1)
    assignment: float = Field(ge=0, le=1)


class ReadinessWorkload(BaseModel):
    unassigned: int
    by_owner: dict[str, int]


class BidReadinessSummary(BaseModel):
    formula_version: str
    project_id: str
    project_name: str
    generated_at: datetime
    source_fingerprint: str
    score_label: str = "response_readiness"
    readiness_score: float = Field(ge=0, le=100)
    counts: ReadinessCounts
    scores: ReadinessScores
    requirements: list[ReadinessRequirementRead]
    mandatory_gaps: list[ReadinessRequirementRead]
    evidence_gaps: list[ReadinessRequirementRead]
    contradictions: list[ReadinessRequirementRead]
    overdue: list[ReadinessRequirementRead]
    qualifications: list[ReadinessRequirementRead]
    workload: ReadinessWorkload


class ReadinessPackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    version_number: int
    formula_version: str
    source_fingerprint: str
    status: str
    summary_json: dict
    xlsx_storage_key: str | None
    docx_storage_key: str | None
    generated_by_user_id: str | None
    created_at: datetime

