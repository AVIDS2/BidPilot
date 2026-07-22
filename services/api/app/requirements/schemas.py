from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BidRequirementProfileInput(BaseModel):
    bid_category: str = "technical"
    is_mandatory: bool = False
    score_weight: float | None = Field(default=None, ge=0)
    risk_level: str = "normal"
    deadline_at: datetime | None = None
    submission_metadata_json: dict | None = None


class BidRequirementProfileUpdate(BaseModel):
    bid_category: str | None = None
    is_mandatory: bool | None = None
    score_weight: float | None = Field(default=None, ge=0)
    risk_level: str | None = None
    deadline_at: datetime | None = None
    submission_metadata_json: dict | None = None


class BidRequirementProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    requirement_id: str
    bid_category: str
    is_mandatory: bool
    score_weight: float | None
    risk_level: str
    coverage_status: str
    evidence_status: str
    deadline_at: datetime | None
    submission_metadata_json: dict | None
    updated_at: datetime


class RequirementItemCreate(BaseModel):
    project_id: str
    section_key: str
    requirement_text: str
    original_text: str | None = None
    source_document_id: str | None = None
    source_locator_json: dict | None = None
    priority: str = "normal"
    owner_user_id: str | None = None
    reviewer_user_id: str | None = None
    due_at: datetime | None = None
    extraction_confidence: float | None = Field(default=None, ge=0, le=1)
    bid_profile: BidRequirementProfileInput | None = None


class RequirementItemUpdate(BaseModel):
    lock_version: int | None = Field(default=None, ge=1)
    requirement_text: str | None = None
    original_text: str | None = None
    source_document_id: str | None = None
    source_locator_json: dict | None = None
    priority: str | None = None
    section_key: str | None = None
    status: str | None = None
    owner_user_id: str | None = None
    reviewer_user_id: str | None = None
    due_at: datetime | None = None
    verification_status: str | None = None
    extraction_confidence: float | None = Field(default=None, ge=0, le=1)
    bid_profile: BidRequirementProfileUpdate | None = None


class RequirementItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    section_key: str
    requirement_text: str
    original_text: str | None
    source_document_id: str | None
    source_document_name: str | None
    source_locator_json: dict | None
    priority: str
    status: str
    owner_user_id: str | None
    reviewer_user_id: str | None
    due_at: datetime | None
    verification_status: str
    extraction_confidence: float | None
    lock_version: int
    updated_at: datetime
    bid_profile: BidRequirementProfileRead | None = None


class RequirementEvidenceLinkCreate(BaseModel):
    evidence_id: str
    relation_type: str = "supports"


class RequirementEvidenceLinkRead(BaseModel):
    id: str
    requirement_id: str
    evidence_id: str
    relation_type: str
    verification_status: str
    quote_text: str
    source_document_id: str | None
    source_document_name: str | None
    locator_json: dict | None
    confidence: float | None
    created_at: datetime


class RequirementEvidenceLinkUpdate(BaseModel):
    verification_status: str


class RequirementDecisionCreate(BaseModel):
    decision_type: str
    rationale: str = Field(min_length=3)


class RequirementDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    requirement_id: str
    decision_type: str
    rationale: str
    status: str
    requested_by_user_id: str
    approved_by_user_id: str | None
    created_at: datetime
    resolved_at: datetime | None


class RequirementClaimCreate(BaseModel):
    claim_text: str = Field(min_length=3)
    claim_type: str = "factual"
    coverage_role: str = "direct"
    evidence_ids: list[str] = Field(default_factory=list, max_length=100)


class RequirementClaimRead(BaseModel):
    id: str
    project_id: str
    requirement_id: str
    claim_text: str
    claim_type: str
    status: str
    coverage_role: str
    section_version_id: str | None
    generation_run_id: str | None
    created_by_actor: str
    created_by_user_id: str | None
    evidence_ids: list[str]
    created_at: datetime
    updated_at: datetime


class ClaimReviewQueueItemRead(BaseModel):
    """A review target without exposing the underlying draft claim text."""

    id: str
    claim_type: str
    status: str
    created_by_actor: str
    section_version_id: str | None
    requirement_ids: list[str]
    evidence_count: int
    blocked_evidence_count: int
    ready_to_verify: bool


class ClaimReviewQueueRead(BaseModel):
    project_id: str
    count: int
    ready_to_verify_count: int
    blocked_by_evidence_count: int
    items: list[ClaimReviewQueueItemRead] = Field(default_factory=list)
    truncated: bool = False


class RequirementDetailRead(RequirementItemRead):
    evidence_links: list[RequirementEvidenceLinkRead] = Field(default_factory=list)
    claims: list[RequirementClaimRead] = Field(default_factory=list)
    decisions: list[RequirementDecisionRead] = Field(default_factory=list)


class RequirementBulkAssign(BaseModel):
    requirement_ids: list[str] = Field(min_length=1, max_length=200)
    lock_versions: dict[str, int] = Field(default_factory=dict)
    owner_user_id: str | None = None
    reviewer_user_id: str | None = None

    @model_validator(mode="after")
    def require_assignment_and_versions(self) -> "RequirementBulkAssign":
        if not ({"owner_user_id", "reviewer_user_id"} & self.model_fields_set):
            raise ValueError("owner_user_id or reviewer_user_id must be provided")
        if set(self.requirement_ids) != set(self.lock_versions):
            raise ValueError("lock_versions must contain every requirement id")
        return self
