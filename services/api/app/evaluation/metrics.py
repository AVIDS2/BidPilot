"""Deterministic BidBench scoring independent of model providers."""

from __future__ import annotations

import unicodedata

from pydantic import BaseModel, ConfigDict

from contracts import (
    BidBenchCandidate,
    BidBenchCandidateRequirement,
    BidBenchDataset,
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
    expected_evidence_links: int
    candidate_evidence_links: int
    true_positive_evidence_links: int
    accepted_claims: int
    unsupported_claims: int


class BidBenchMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    formula_version: str = "1.0"
    matching_policy: str = "explicit-id-or-normalized-exact-v1"
    counts: BidBenchScoreCounts
    requirement_recall: float
    requirement_precision: float
    requirement_f1: float
    mandatory_recall: float
    scored_recall: float
    source_association_accuracy: float
    evidence_precision: float
    evidence_recall: float
    evidence_f1: float
    unsupported_claim_rate: float | None
    claim_grounding_rate: float | None
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
    for candidate_requirement, truth in matches:
        truth_sources = {locator.source_id for locator in truth.locators}
        candidate_sources = {locator.source_id for locator in candidate_requirement.locators}
        if truth_sources & candidate_sources:
            correct_sources += 1
    source_accuracy = _ratio(correct_sources, len(matches))

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
    unsupported_claims = [
        claim
        for claim in accepted_claims
        if not claim.is_inference and not claim.evidence_ids
    ]
    unsupported_claim_rate = (
        _ratio(len(unsupported_claims), len(accepted_claims)) if accepted_claims else None
    )
    claim_grounding_rate = (
        1.0 - unsupported_claim_rate if unsupported_claim_rate is not None else None
    )

    completeness_score = _average([requirement_recall, mandatory_recall, scored_recall])
    traceability_components = [source_accuracy, evidence_f1]
    if claim_grounding_rate is not None:
        traceability_components.append(claim_grounding_rate)
    traceability_score = _average(traceability_components)
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
            expected_evidence_links=len(expected_evidence),
            candidate_evidence_links=len(candidate_evidence),
            true_positive_evidence_links=len(true_positive_evidence),
            accepted_claims=len(accepted_claims),
            unsupported_claims=len(unsupported_claims),
        ),
        requirement_recall=requirement_recall,
        requirement_precision=requirement_precision,
        requirement_f1=requirement_f1,
        mandatory_recall=mandatory_recall,
        scored_recall=scored_recall,
        source_association_accuracy=source_accuracy,
        evidence_precision=evidence_precision,
        evidence_recall=evidence_recall,
        evidence_f1=evidence_f1,
        unsupported_claim_rate=unsupported_claim_rate,
        claim_grounding_rate=claim_grounding_rate,
        completeness_score=completeness_score,
        traceability_score=traceability_score,
        combined_score=combined_score,
    )


def _match_requirements(
    truth_requirements: list[BidBenchRequirement],
    candidate_requirements: list[BidBenchCandidateRequirement],
) -> list[tuple[BidBenchCandidateRequirement, BidBenchRequirement]]:
    truth_by_id = {requirement.id: requirement for requirement in truth_requirements}
    truth_by_normalized: dict[str, list[BidBenchRequirement]] = {}
    for requirement in truth_requirements:
        truth_by_normalized.setdefault(_normalize_text(requirement.normalized_text), []).append(requirement)

    matches: list[tuple[BidBenchCandidateRequirement, BidBenchRequirement]] = []
    matched_truth_ids: set[str] = set()

    for candidate_requirement in candidate_requirements:
        truth: BidBenchRequirement | None = None
        if candidate_requirement.ground_truth_id:
            if candidate_requirement.ground_truth_id not in truth_by_id:
                raise ValueError(
                    f"candidate requirement {candidate_requirement.id!r} references unknown ground_truth_id "
                    f"{candidate_requirement.ground_truth_id!r}"
                )
            truth = truth_by_id[candidate_requirement.ground_truth_id]
        else:
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
