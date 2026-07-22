"""Deterministic BidBench scoring independent of model providers."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from contracts import (
    BidBenchCandidate,
    BidBenchCandidateClaim,
    BidBenchCandidateRequirement,
    BidBenchDataset,
    BidBenchLocator,
    BidBenchRequirement,
    RequirementType,
)


class BidBenchScoreCounts(BaseModel):
    model_config = ConfigDict(frozen=True)

    ground_truth_requirements: int
    candidate_requirements: int
    matched_requirements: int
    mandatory_requirements: int
    matched_mandatory_requirements: int
    scored_requirements: int
    matched_scored_requirements: int
    correctly_classified_requirements: int
    correctly_covered_requirements: int
    expected_evidence_links: int
    candidate_evidence_links: int
    true_positive_evidence_links: int
    accepted_claims: int
    unsupported_claims: int
    traceable_claims: int = 0
    untraceable_claims: int = 0
    claims_with_unknown_requirement_refs: int = 0
    claims_with_missing_evidence_refs: int = 0
    claims_with_unsupported_requirement_evidence_pairs: int = 0


class BidBenchMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    formula_version: str = "2.1"
    matching_policy: str = "normalized-exact-v2"
    counts: BidBenchScoreCounts
    requirement_recall: float
    requirement_precision: float
    requirement_f1: float
    mandatory_recall: float
    scored_recall: float
    scored_weight_recall: float
    classification_accuracy: float
    coverage_accuracy: float
    source_association_accuracy: float
    evidence_precision: float
    evidence_recall: float
    evidence_f1: float
    unsupported_claim_rate: float | None
    claim_grounding_rate: float | None
    claim_trace_integrity_rate: float | None = None
    completeness_score: float
    traceability_score: float
    combined_score: float


def score_candidate(dataset: BidBenchDataset, candidate: BidBenchCandidate) -> BidBenchMetrics:
    if dataset.dataset_id != candidate.dataset_id:
        raise ValueError(
            f"candidate dataset_id {candidate.dataset_id!r} does not match {dataset.dataset_id!r}"
        )

    matches = _match_requirements(dataset.requirements, candidate.requirements)
    matched_truth_ids = {truth.id for _, truth in matches}

    mandatory_ids = {requirement.id for requirement in dataset.requirements if requirement.is_mandatory}
    scored_ids = {
        requirement.id
        for requirement in dataset.requirements
        if requirement.requirement_type == RequirementType.SCORED
    }

    requirement_recall = _ratio(len(matches), len(dataset.requirements))
    requirement_precision = _ratio(len(matches), len(candidate.requirements))
    requirement_f1 = _f1(requirement_precision, requirement_recall)
    mandatory_recall = _ratio(len(matched_truth_ids & mandatory_ids), len(mandatory_ids), empty=1.0)
    scored_recall = _ratio(len(matched_truth_ids & scored_ids), len(scored_ids), empty=1.0)

    correct_sources = 0
    correctly_classified = 0
    correctly_covered = 0
    for candidate_requirement, truth in matches:
        if candidate_requirement.requirement_type == truth.requirement_type and (
            candidate_requirement.is_mandatory == truth.is_mandatory
        ):
            correctly_classified += 1
        if candidate_requirement.coverage_status == truth.expected_coverage:
            correctly_covered += 1
        if any(
            _locator_matches(candidate_locator, truth_locator)
            for candidate_locator in candidate_requirement.locators
            for truth_locator in truth.locators
        ):
            correct_sources += 1
    source_accuracy = _ratio(correct_sources, len(matches))
    classification_accuracy = _ratio(correctly_classified, len(matches))
    coverage_accuracy = _ratio(correctly_covered, len(matches))

    total_scored_weight = sum(
        requirement.score_weight or 0
        for requirement in dataset.requirements
        if requirement.requirement_type == RequirementType.SCORED
    )
    matched_scored_weight = sum(
        truth.score_weight or 0
        for _, truth in matches
        if truth.requirement_type == RequirementType.SCORED
    )
    scored_weight_recall = _ratio(
        matched_scored_weight,
        total_scored_weight,
        empty=1.0,
    )

    expected_evidence = {
        (requirement.id, evidence_id)
        for requirement in dataset.requirements
        for evidence_id in requirement.expected_evidence_ids
    }
    matched_by_candidate_id = {candidate_requirement.id: truth.id for candidate_requirement, truth in matches}
    candidate_evidence = set()
    for candidate_requirement in candidate.requirements:
        truth_id = matched_by_candidate_id.get(
            candidate_requirement.id,
            f"unmatched:{candidate_requirement.id}",
        )
        candidate_evidence.update((truth_id, evidence_id) for evidence_id in candidate_requirement.evidence_ids)

    true_positive_evidence = expected_evidence & candidate_evidence
    evidence_precision = _ratio(
        len(true_positive_evidence),
        len(candidate_evidence),
        empty=1.0 if not expected_evidence else 0.0,
    )
    evidence_recall = _ratio(
        len(true_positive_evidence),
        len(expected_evidence),
        empty=1.0,
    )
    evidence_f1 = _f1(evidence_precision, evidence_recall)

    accepted_claims = [claim for claim in candidate.claims if claim.accepted]
    valid_evidence_ids = {evidence.id for evidence in dataset.evidence}
    unsupported_claims = [
        claim
        for claim in accepted_claims
        if not claim.is_inference
        and not any(evidence_id in valid_evidence_ids for evidence_id in claim.evidence_ids)
    ]
    unsupported_claim_rate = (
        _ratio(len(unsupported_claims), len(accepted_claims)) if accepted_claims else None
    )
    claim_grounding_rate = (
        1.0 - unsupported_claim_rate if unsupported_claim_rate is not None else None
    )
    claim_trace = _score_claim_trace_integrity(
        accepted_claims,
        matched_by_candidate_id=matched_by_candidate_id,
        valid_evidence_ids=valid_evidence_ids,
        valid_requirement_evidence_pairs={
            (requirement_id, evidence.id)
            for evidence in dataset.evidence
            for requirement_id in evidence.supports_requirement_ids
        },
    )

    completeness_score = _average(
        [
            requirement_f1,
            mandatory_recall,
            scored_weight_recall,
            classification_accuracy,
            coverage_accuracy,
        ]
    )
    traceability_score = _average([source_accuracy, evidence_f1])
    combined_score = 0.6 * completeness_score + 0.4 * traceability_score

    return BidBenchMetrics(
        counts=BidBenchScoreCounts(
            ground_truth_requirements=len(dataset.requirements),
            candidate_requirements=len(candidate.requirements),
            matched_requirements=len(matches),
            mandatory_requirements=len(mandatory_ids),
            matched_mandatory_requirements=len(matched_truth_ids & mandatory_ids),
            scored_requirements=len(scored_ids),
            matched_scored_requirements=len(matched_truth_ids & scored_ids),
            correctly_classified_requirements=correctly_classified,
            correctly_covered_requirements=correctly_covered,
            expected_evidence_links=len(expected_evidence),
            candidate_evidence_links=len(candidate_evidence),
            true_positive_evidence_links=len(true_positive_evidence),
            accepted_claims=len(accepted_claims),
            unsupported_claims=len(unsupported_claims),
            traceable_claims=claim_trace.traceable_claims,
            untraceable_claims=claim_trace.untraceable_claims,
            claims_with_unknown_requirement_refs=claim_trace.claims_with_unknown_requirement_refs,
            claims_with_missing_evidence_refs=claim_trace.claims_with_missing_evidence_refs,
            claims_with_unsupported_requirement_evidence_pairs=(
                claim_trace.claims_with_unsupported_requirement_evidence_pairs
            ),
        ),
        requirement_recall=requirement_recall,
        requirement_precision=requirement_precision,
        requirement_f1=requirement_f1,
        mandatory_recall=mandatory_recall,
        scored_recall=scored_recall,
        scored_weight_recall=scored_weight_recall,
        classification_accuracy=classification_accuracy,
        coverage_accuracy=coverage_accuracy,
        source_association_accuracy=source_accuracy,
        evidence_precision=evidence_precision,
        evidence_recall=evidence_recall,
        evidence_f1=evidence_f1,
        unsupported_claim_rate=unsupported_claim_rate,
        claim_grounding_rate=claim_grounding_rate,
        claim_trace_integrity_rate=claim_trace.claim_trace_integrity_rate,
        completeness_score=completeness_score,
        traceability_score=traceability_score,
        combined_score=combined_score,
    )


@dataclass(frozen=True)
class _ClaimTraceIntegrity:
    traceable_claims: int
    untraceable_claims: int
    claims_with_unknown_requirement_refs: int
    claims_with_missing_evidence_refs: int
    claims_with_unsupported_requirement_evidence_pairs: int
    claim_trace_integrity_rate: float | None


def _score_claim_trace_integrity(
    claims: list[BidBenchCandidateClaim],
    *,
    matched_by_candidate_id: dict[str, str],
    valid_evidence_ids: set[str],
    valid_requirement_evidence_pairs: set[tuple[str, str]],
) -> _ClaimTraceIntegrity:
    """Score the explicit Requirement -> Evidence -> Claim contract only."""
    traceable_claims = 0
    unknown_requirement_refs = 0
    missing_evidence_refs = 0
    unsupported_pairs = 0

    for claim in claims:
        candidate_requirement_ids = set(claim.requirement_ids)
        evidence_ids = set(claim.evidence_ids)
        if not candidate_requirement_ids or not candidate_requirement_ids.issubset(
            matched_by_candidate_id
        ):
            unknown_requirement_refs += 1
            continue
        if not evidence_ids or not evidence_ids.issubset(valid_evidence_ids):
            missing_evidence_refs += 1
            continue

        truth_requirement_ids = {
            matched_by_candidate_id[requirement_id]
            for requirement_id in candidate_requirement_ids
        }
        requirement_evidence_pairs = {
            (requirement_id, evidence_id)
            for requirement_id in truth_requirement_ids
            for evidence_id in evidence_ids
        }
        if not requirement_evidence_pairs.issubset(valid_requirement_evidence_pairs):
            unsupported_pairs += 1
            continue
        traceable_claims += 1

    untraceable_claims = len(claims) - traceable_claims
    return _ClaimTraceIntegrity(
        traceable_claims=traceable_claims,
        untraceable_claims=untraceable_claims,
        claims_with_unknown_requirement_refs=unknown_requirement_refs,
        claims_with_missing_evidence_refs=missing_evidence_refs,
        claims_with_unsupported_requirement_evidence_pairs=unsupported_pairs,
        claim_trace_integrity_rate=(
            _ratio(traceable_claims, len(claims)) if claims else None
        ),
    )


def _match_requirements(
    truth_requirements: list[BidBenchRequirement],
    candidate_requirements: list[BidBenchCandidateRequirement],
) -> list[tuple[BidBenchCandidateRequirement, BidBenchRequirement]]:
    truth_by_normalized: dict[str, list[BidBenchRequirement]] = {}
    for requirement in truth_requirements:
        truth_by_normalized.setdefault(_normalize_text(requirement.normalized_text), []).append(requirement)

    matches: list[tuple[BidBenchCandidateRequirement, BidBenchRequirement]] = []
    matched_truth_ids: set[str] = set()

    for candidate_requirement in candidate_requirements:
        normalized = _normalize_text(candidate_requirement.normalized_text)
        truth = next(
            (
                item
                for item in truth_by_normalized.get(normalized, [])
                if item.id not in matched_truth_ids
            ),
            None,
        )

        if truth is None or truth.id in matched_truth_ids:
            continue
        matches.append((candidate_requirement, truth))
        matched_truth_ids.add(truth.id)

    return matches


def _locator_matches(candidate: BidBenchLocator, truth: BidBenchLocator) -> bool:
    if candidate.source_id != truth.source_id:
        return False
    checks: list[bool] = []
    if candidate.page is not None and truth.page is not None:
        checks.append(candidate.page == truth.page)
    if candidate.section and truth.section:
        checks.append(_normalize_text(candidate.section) == _normalize_text(truth.section))
    if candidate.table and truth.table:
        checks.append(_normalize_text(candidate.table) == _normalize_text(truth.table))
    if candidate.text_anchor and truth.text_anchor:
        candidate_anchor = _normalize_text(candidate.text_anchor)
        truth_anchor = _normalize_text(truth.text_anchor)
        checks.append(
            candidate_anchor == truth_anchor
            or (len(truth_anchor) >= 8 and truth_anchor in candidate_anchor)
            or (len(candidate_anchor) >= 8 and candidate_anchor in truth_anchor)
        )
    if candidate.bbox is not None and truth.bbox is not None:
        checks.append(_bbox_iou(candidate.bbox, truth.bbox) >= 0.5)
    return any(checks)


def _bbox_iou(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> float:
    left_x1, left_y1, left_x2, left_y2 = left
    right_x1, right_y1, right_x2, right_y2 = right
    intersection_width = max(0.0, min(left_x2, right_x2) - max(left_x1, right_x1))
    intersection_height = max(0.0, min(left_y2, right_y2) - max(left_y1, right_y1))
    intersection = intersection_width * intersection_height
    left_area = max(0.0, left_x2 - left_x1) * max(0.0, left_y2 - left_y1)
    right_area = max(0.0, right_x2 - right_x1) * max(0.0, right_y2 - right_y1)
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(
        character
        for character in normalized
        if not character.isspace() and not unicodedata.category(character).startswith("P")
    )


def _ratio(numerator: int, denominator: int, *, empty: float = 0.0) -> float:
    if denominator == 0:
        return empty
    return numerator / denominator


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


__all__ = ["BidBenchMetrics", "BidBenchScoreCounts", "score_candidate"]
