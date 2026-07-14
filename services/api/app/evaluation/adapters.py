"""Adapters that normalize existing BidPilot outputs into BidBench candidates."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from contracts import BidBenchCandidate, BidBenchCandidateRequirement


class CurrentRequirementSnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    section_key: str = Field(min_length=1)
    requirement_text: str = Field(min_length=1)
    priority: str = "normal"
    status: str = "draft"


_REQUIREMENT_LIST = TypeAdapter(list[CurrentRequirementSnapshot])


def build_candidate_from_requirement_snapshot(
    *,
    snapshot_path: Path,
    dataset_id: str,
    candidate_id: str,
    git_commit: str | None = None,
) -> BidBenchCandidate:
    """Convert the current Requirement API response into a saved candidate.

    The current API does not expose requirement source locators or evidence links.
    The adapter intentionally leaves those fields empty instead of inventing
    traceability, making the baseline weakness visible in the score.
    """

    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("requirements", [])
    requirements = _REQUIREMENT_LIST.validate_python(payload)

    candidate_requirements = []
    for requirement in requirements:
        is_mandatory = requirement.priority.casefold() == "high"
        candidate_requirements.append(
            BidBenchCandidateRequirement(
                id=requirement.id,
                normalized_text=requirement.requirement_text,
                requirement_type="mandatory" if is_mandatory else "technical",
                is_mandatory=is_mandatory,
                coverage_status="uncovered",
                locators=[],
                evidence_ids=[],
            )
        )

    return BidBenchCandidate(
        schema_version="1.0",
        dataset_id=dataset_id,
        candidate_id=candidate_id,
        system_name="bidpilot-current-requirement-api",
        git_commit=git_commit,
        prompt_version="current-requirement-api-v1",
        generated_at=datetime.now(UTC),
        requirements=candidate_requirements,
        claims=[],
    )


__all__ = ["CurrentRequirementSnapshot", "build_candidate_from_requirement_snapshot"]
