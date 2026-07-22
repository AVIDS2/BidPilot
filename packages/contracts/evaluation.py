"""Redacted provenance contracts for offline Agent quality evidence."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


_EVIDENCE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$"


class EvaluationCaptureKind(StrEnum):
    """How an evaluation candidate or runtime capture was produced."""

    CURRENT_PIPELINE = "current_pipeline"
    REVIEWED_SNAPSHOT = "reviewed_snapshot"
    CONTROL_FIXTURE = "control_fixture"


class EvaluationReviewLevel(StrEnum):
    """Human review depth recorded without storing reviewer identities."""

    UNREVIEWED = "unreviewed"
    SINGLE_REVIEWER = "single_reviewer"
    TWO_PERSON_REVIEW = "two_person_review"


class EvaluationEvidenceProvenance(BaseModel):
    """Redacted metadata needed to decide whether evidence can promote a release."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    evidence_set_id: str = Field(min_length=3, max_length=160, pattern=_EVIDENCE_ID_PATTERN)
    capture_id: str = Field(min_length=3, max_length=160, pattern=_EVIDENCE_ID_PATTERN)
    capture_kind: EvaluationCaptureKind
    review_level: EvaluationReviewLevel
    evaluator_version: str = Field(min_length=1, max_length=100)
    attestation_ref: str | None = Field(default=None, min_length=3, max_length=500)


__all__ = [
    "EvaluationCaptureKind",
    "EvaluationEvidenceProvenance",
    "EvaluationReviewLevel",
]
