from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.evaluation.claim_integrity_runtime_capture import (
    ClaimIntegrityRuntimeCaptureManifest,
    ClaimIntegrityRuntimeClaimMap,
    ClaimIntegrityRuntimeEvidenceMap,
    ClaimIntegrityRuntimeRequirementMap,
    ClaimIntegrityRuntimeSourceMap,
    capture_claim_integrity_runtime_candidate,
    fixture_fingerprint,
)
from app.evaluation.metrics import score_candidate
from app.models import (
    BidRequirementProfile,
    Bundle,
    Claim,
    ClaimEvidenceLink,
    Deliverable,
    DeliverableSection,
    Evidence,
    ExecutionRun,
    Project,
    RequirementClaimLink,
    RequirementEvidenceLink,
    RequirementItem,
    RuntimeRun,
    SectionVersion,
    SourceDocument,
)
from contracts import (
    BidBenchDataset,
    BidBenchEvidence,
    BidBenchLocator,
    BidBenchRequirement,
    BidBenchSource,
    CoverageStatus,
    EvaluationCaptureKind,
    EvaluationEvidenceProvenance,
    EvaluationReviewLevel,
    RequirementType,
)


_MODEL = "controlled-claim-model"


def _dataset() -> BidBenchDataset:
    locator = BidBenchLocator(
        source_id="rfp",
        section="3.1",
        text_anchor="ISO 27001 certificate",
    )
    return BidBenchDataset(
        schema_version="1.0",
        dataset_id="claim-runtime-capture-v1",
        title="Claim runtime capture fixture",
        language="en",
        dataset_role="development",
        origin_type="synthetic",
        provenance="Synthetic controlled Claim Integrity capture fixture.",
        license_id="CC0-1.0",
        sources=(
            BidBenchSource(
                id="rfp",
                path="sources/rfp.txt",
                title="Synthetic RFP",
                source_type="text",
                sha256="a" * 64,
            ),
        ),
        requirements=(
            BidBenchRequirement(
                id="req-iso",
                original_text="The bidder must provide an ISO 27001 certificate.",
                normalized_text="Provide a current ISO 27001 certificate.",
                requirement_type=RequirementType.QUALIFICATION,
                is_mandatory=True,
                expected_coverage=CoverageStatus.COVERED,
                locators=(locator,),
                expected_evidence_ids=("ev-iso",),
            ),
        ),
        evidence=(
            BidBenchEvidence(
                id="ev-iso",
                source_id="rfp",
                text="ISO 27001 certificate reference.",
                locator=locator,
                supports_requirement_ids=("req-iso",),
            ),
        ),
    )


def _seed_capture_records(test_db, default_org_id: str, default_user_id: str) -> dict[str, str]:
    suffix = uuid4().hex[:10]
    project = Project(
        id=str(uuid4()),
        org_id=default_org_id,
        slug=f"claim-capture-{suffix}",
        name="Claim Capture",
        scenario_package="bidpilot",
    )
    test_db.add(project)
    test_db.flush()
    bundle = Bundle(project_id=project.id, label="Internal source bundle", source_type="upload")
    test_db.add(bundle)
    test_db.flush()
    source = SourceDocument(
        bundle_id=bundle.id,
        storage_key="private/claim-capture.txt",
        mime_type="text/plain",
        checksum="b" * 64,
        original_filename="internal-tender-source.txt",
    )
    test_db.add(source)
    test_db.flush()
    requirement = RequirementItem(
        id=str(uuid4()),
        project_id=project.id,
        section_key="qualification",
        requirement_text="Provide a current ISO 27001 certificate.",
        original_text="Private source requirement body must not be exported.",
        source_document_id=source.id,
        source_locator_json={"section": "3.1", "text_anchor": "ISO 27001 certificate"},
        priority="high",
        extraction_confidence=0.97,
    )
    requirement.bid_profile = BidRequirementProfile(
        bid_category="qualification",
        is_mandatory=True,
        coverage_status="covered",
        evidence_status="sufficient",
    )
    test_db.add(requirement)
    test_db.flush()
    evidence = Evidence(
        id=str(uuid4()),
        project_id=project.id,
        source_document_id=source.id,
        quote_text="Private evidence quotation must not be exported.",
        locator_json={"section": "3.1"},
        confidence=0.91,
    )
    test_db.add(evidence)
    test_db.flush()
    deliverable = Deliverable(project_id=project.id, type="proposal", title="Private deliverable")
    test_db.add(deliverable)
    test_db.flush()
    section = DeliverableSection(
        deliverable_id=deliverable.id,
        section_key="qualification",
        title="Qualification",
    )
    test_db.add(section)
    run = ExecutionRun(
        id=str(uuid4()),
        project_id=project.id,
        run_type="draft_section",
        status="succeeded",
    )
    test_db.add(run)
    test_db.flush()
    section_version = SectionVersion(
        id=str(uuid4()),
        deliverable_section_id=section.id,
        version_number=1,
        content_markdown="Private generated section content must not be exported.",
        generation_run_id=run.id,
    )
    test_db.add(section_version)
    test_db.flush()
    claim = Claim(
        id=str(uuid4()),
        project_id=project.id,
        claim_text="Private generated claim must never appear in the benchmark candidate.",
        claim_type="factual",
        status="verified",
        section_version_id=section_version.id,
        generation_run_id=run.id,
        created_by_actor="ai",
    )
    test_db.add(claim)
    test_db.add_all(
        [
            RequirementEvidenceLink(
                requirement_id=requirement.id,
                evidence_id=evidence.id,
                relation_type="supports",
                verification_status="verified",
            ),
            RequirementClaimLink(requirement_id=requirement.id, claim_id=claim.id),
            ClaimEvidenceLink(claim_id=claim.id, evidence_id=evidence.id),
        ]
    )
    test_db.add(
        RuntimeRun(
            id=str(uuid4()),
            kind="workflow_bridge",
            status="succeeded",
            org_id=default_org_id,
            user_id=default_user_id,
            project_id=project.id,
            execution_run_id=run.id,
            engine="langgraph_workflow",
            trace_id=f"claim-capture-{suffix}",
            model=_MODEL,
            policy_snapshot_json={"approval_mode": "risky_only"},
        )
    )
    run.output_json = {
        "section_version_id": section_version.id,
        "claim_integrity_status": "proposed",
        "claim_count": 1,
    }
    test_db.commit()
    return {
        "project_id": project.id,
        "run_id": run.id,
        "section_version_id": section_version.id,
        "requirement_id": requirement.id,
        "source_document_id": source.id,
        "evidence_id": evidence.id,
        "claim_id": claim.id,
        "runtime_run_id": test_db.scalar(
            select(RuntimeRun.id).where(RuntimeRun.execution_run_id == run.id)
        ),
        "claim_text": claim.claim_text,
        "evidence_quote": evidence.quote_text,
        "source_filename": source.original_filename,
    }


def _manifest(dataset: BidBenchDataset, records: dict[str, str]) -> ClaimIntegrityRuntimeCaptureManifest:
    return ClaimIntegrityRuntimeCaptureManifest(
        dataset_id=dataset.dataset_id,
        fixture_fingerprint=fixture_fingerprint(dataset),
        runtime_project_id=records["project_id"],
        execution_run_id=records["run_id"],
        section_version_id=records["section_version_id"],
        candidate_id="claim-runtime-candidate-1",
        requirements=(
            ClaimIntegrityRuntimeRequirementMap(
                runtime_requirement_id=records["requirement_id"],
                candidate_requirement_id="candidate-req-iso",
                benchmark_requirement_id="req-iso",
            ),
        ),
        source_documents=(
            ClaimIntegrityRuntimeSourceMap(
                runtime_source_document_id=records["source_document_id"],
                candidate_source_id="rfp",
                benchmark_source_id="rfp",
            ),
        ),
        evidence=(
            ClaimIntegrityRuntimeEvidenceMap(
                runtime_evidence_id=records["evidence_id"],
                candidate_evidence_id="ev-iso",
                benchmark_evidence_id="ev-iso",
            ),
        ),
        claims=(
            ClaimIntegrityRuntimeClaimMap(
                runtime_claim_id=records["claim_id"],
                candidate_claim_id="candidate-claim-iso",
            ),
        ),
        git_commit="a" * 40,
        provider="controlled-provider",
        model=_MODEL,
        provenance=EvaluationEvidenceProvenance(
            evidence_set_id="claim-runtime-capture",
            capture_id="claim-runtime-capture-1",
            capture_kind=EvaluationCaptureKind.CURRENT_PIPELINE,
            review_level=EvaluationReviewLevel.TWO_PERSON_REVIEW,
            evaluator_version="claim-integrity-runtime-capture-v1",
            attestation_ref="ci:claim-runtime-capture-1",
        ),
    )


def test_claim_runtime_capture_redacts_business_text_and_durable_ids(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    dataset = _dataset()
    records = _seed_capture_records(test_db, default_org_id, default_user_id)

    candidate = capture_claim_integrity_runtime_candidate(test_db, dataset, _manifest(dataset, records))

    assert candidate.requirements[0].id == "candidate-req-iso"
    assert candidate.requirements[0].normalized_text == "Provide a current ISO 27001 certificate."
    assert candidate.claims[0].id == "candidate-claim-iso"
    assert candidate.claims[0].text == "redacted-claim-candidate-claim-iso"
    assert candidate.claims[0].requirement_ids == ["candidate-req-iso"]
    assert candidate.claims[0].evidence_ids == ["ev-iso"]

    serialized = candidate.model_dump_json()
    for forbidden in (
        records["project_id"],
        records["run_id"],
        records["section_version_id"],
        records["requirement_id"],
        records["source_document_id"],
        records["evidence_id"],
        records["claim_id"],
        records["runtime_run_id"],
        records["claim_text"],
        records["evidence_quote"],
        records["source_filename"],
    ):
        assert forbidden not in serialized

    report = score_candidate(dataset, candidate)
    assert report.claim_trace_integrity_rate == 1.0


def test_claim_runtime_capture_preserves_unknown_claim_evidence_as_a_bad_score(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    dataset = _dataset()
    records = _seed_capture_records(test_db, default_org_id, default_user_id)
    extra_evidence = Evidence(
        id=str(uuid4()),
        project_id=records["project_id"],
        quote_text="A second private quote that is not in the frozen fixture.",
    )
    test_db.add(extra_evidence)
    test_db.add(ClaimEvidenceLink(claim_id=records["claim_id"], evidence_id=extra_evidence.id))
    test_db.commit()
    manifest = _manifest(dataset, records).model_copy(
        update={
            "evidence": (
                ClaimIntegrityRuntimeEvidenceMap(
                    runtime_evidence_id=records["evidence_id"],
                    candidate_evidence_id="ev-iso",
                    benchmark_evidence_id="ev-iso",
                ),
                ClaimIntegrityRuntimeEvidenceMap(
                    runtime_evidence_id=extra_evidence.id,
                    candidate_evidence_id="opaque-evidence-1",
                ),
            )
        }
    )

    candidate = capture_claim_integrity_runtime_candidate(test_db, dataset, manifest)

    report = score_candidate(dataset, candidate)
    assert report.claim_trace_integrity_rate == 0.0
    assert report.counts.claims_with_missing_evidence_refs == 1
    assert "A second private quote" not in candidate.model_dump_json()


def test_claim_runtime_capture_rejects_failed_runtime_bridge(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    dataset = _dataset()
    records = _seed_capture_records(test_db, default_org_id, default_user_id)
    runtime_run = test_db.get(RuntimeRun, records["runtime_run_id"])
    assert runtime_run is not None
    runtime_run.status = "failed"
    test_db.commit()

    with pytest.raises(ValueError, match="runtime bridge scope is invalid"):
        capture_claim_integrity_runtime_candidate(test_db, dataset, _manifest(dataset, records))


def test_claim_runtime_capture_rejects_incomplete_evidence_mapping(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    dataset = _dataset()
    records = _seed_capture_records(test_db, default_org_id, default_user_id)
    manifest = _manifest(dataset, records).model_copy(update={"evidence": ()})

    with pytest.raises(ValueError, match="runtime evidence map does not exactly cover"):
        capture_claim_integrity_runtime_candidate(test_db, dataset, manifest)


def test_claim_runtime_capture_rejects_a_durable_identifier_in_candidate_output(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    dataset = _dataset()
    records = _seed_capture_records(test_db, default_org_id, default_user_id)
    manifest = _manifest(dataset, records).model_copy(
        update={
            "claims": (
                ClaimIntegrityRuntimeClaimMap(
                    runtime_claim_id=records["claim_id"],
                    candidate_claim_id=records["claim_id"],
                ),
            )
        }
    )

    with pytest.raises(ValueError, match="must not reuse durable runtime IDs"):
        capture_claim_integrity_runtime_candidate(test_db, dataset, manifest)


def test_claim_runtime_capture_rejects_claim_from_the_same_run_with_wrong_version(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    dataset = _dataset()
    records = _seed_capture_records(test_db, default_org_id, default_user_id)
    extra_claim = Claim(
        id=str(uuid4()),
        project_id=records["project_id"],
        claim_text="A malformed same-run claim must not be ignored by capture.",
        claim_type="factual",
        status="draft",
        generation_run_id=records["run_id"],
        created_by_actor="ai",
    )
    test_db.add(extra_claim)
    execution_run = test_db.get(ExecutionRun, records["run_id"])
    assert execution_run is not None
    execution_run.output_json = {
        **(execution_run.output_json or {}),
        "claim_count": 2,
    }
    test_db.commit()
    manifest = _manifest(dataset, records).model_copy(
        update={
            "claims": (
                ClaimIntegrityRuntimeClaimMap(
                    runtime_claim_id=records["claim_id"],
                    candidate_claim_id="candidate-claim-iso",
                ),
                ClaimIntegrityRuntimeClaimMap(
                    runtime_claim_id=extra_claim.id,
                    candidate_claim_id="candidate-claim-malformed",
                ),
            )
        }
    )

    with pytest.raises(ValueError, match="claim scope is invalid"):
        capture_claim_integrity_runtime_candidate(test_db, dataset, manifest)
