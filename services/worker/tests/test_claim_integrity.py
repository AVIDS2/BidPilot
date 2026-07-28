from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy import select

from app.adapters.structured_llm import StructuredModelResult
from app.db import SessionLocal
from app.graph.nodes.persist_result import _public_persist_failure, persist_result_node
from app.graph.nodes.quality_reviewer import _parse_review
from app.retrieval.evidence_sets import EvidenceSetScopeError
from app.models import (
    Bundle,
    Claim,
    ClaimEvidenceLink,
    Deliverable,
    DeliverableSection,
    Evidence,
    EvidenceSet,
    EvidenceSetItem,
    ExecutionRun,
    KnowledgeChunk,
    Organization,
    Project,
    RequirementClaimLink,
    RequirementEvidenceLink,
    RequirementItem,
    ReviewThread,
    SectionVersion,
    SourceDocument,
)
from contracts.response_plans import (
    ResponsePlanScopeError,
    capture_response_plan_binding,
    ensure_response_plan_section,
)


def _add_evidence_set(
    db,
    *,
    project_id: str,
    run_id: str,
    section_key: str,
    source: SourceDocument | None = None,
    chunk: KnowledgeChunk | None = None,
) -> EvidenceSet:
    """Create the durable evidence boundary required by persistence tests."""
    evidence_set = EvidenceSet(
        project_id=project_id,
        execution_run_id=run_id,
        section_key=section_key,
        query_text=section_key,
        status="ready" if source is not None and chunk is not None else "missing_evidence",
        degraded_reasons_json=[],
        rejected_reasons_json=[],
        unmet_requirement_ids_json=[],
    )
    db.add(evidence_set)
    db.flush()
    if source is not None and chunk is not None:
        db.add(
            EvidenceSetItem(
                evidence_set_id=evidence_set.id,
                source_document_id=source.id,
                chunk_id=chunk.id,
                source_document_version=int(source.version_number or 1),
                source_document_checksum=source.checksum,
                locator_json={
                    "source_document_id": source.id,
                    "chunk_index": chunk.chunk_index,
                    "validation_status": "verified",
                },
                quote_text=chunk.content,
                retrieval_rank=1,
                retrieval_score=1.0,
                retrieval_methods_json=["test"],
                selected_reason="test fixture",
            )
        )
    return evidence_set


def _add_response_plan_binding(
    db,
    *,
    project_id: str,
    run_id: str,
    evidence_set_id: str,
    section_key: str,
    generation_iteration: int,
) -> dict[str, object]:
    """Build the same immutable planning boundary required by persistence."""
    plan_section = ensure_response_plan_section(
        db,
        project_id=project_id,
        section_key=section_key,
    )
    binding = capture_response_plan_binding(
        db,
        project_id=project_id,
        execution_run_id=run_id,
        evidence_set_id=evidence_set_id,
        response_plan_section_id=plan_section.response_plan_section_id,
        generation_iteration=generation_iteration,
        content_plan={
            "section_key": section_key,
            "summary": "Test-only durable content plan.",
            "outline": ["Evidence-backed draft"],
            "key_points": [],
            "evidence_picks": [],
            "tables": [],
            "figures": [],
            "gaps": [],
        },
    )
    return {
        "response_plan_id": binding.response_plan_id,
        "response_plan_section_id": binding.response_plan_section_id,
        "response_plan_evidence_binding_id": (
            binding.response_plan_evidence_binding_id
        ),
        "response_plan_version": binding.response_plan_version,
    }


def test_persist_failure_hides_internal_error_detail() -> None:
    sensitive_marker = "test-sensitive-marker"

    error_code, message = _public_persist_failure(
        RuntimeError(f"provider detail: {sensitive_marker}")
    )

    assert error_code == "persistence_failed"
    assert sensitive_marker not in message


def test_persist_failure_keeps_durable_boundary_error_codes() -> None:
    evidence_code, evidence_message = _public_persist_failure(
        EvidenceSetScopeError("evidence_set_project_scope_invalid")
    )
    plan_code, plan_message = _public_persist_failure(
        ResponsePlanScopeError("response_plan_binding_project_scope_invalid")
    )

    assert evidence_code == "evidence_set_unavailable"
    assert "证据集" in evidence_message
    assert plan_code == "response_plan_unavailable"
    assert "响应计划" in plan_message


def test_review_claim_candidates_reject_unknown_aliases_and_invented_text() -> None:
    draft = "BidPilot uses AES-256 encryption for data at rest."
    review, candidates = _parse_review(
        StructuredModelResult(
            content=json.dumps(
                {
                    "passed": True,
                    "issues": [],
                    "suggestions": [],
                    "overall_score": 0.92,
                    "claims": [
                        {
                            "text": "BidPilot uses AES-256 encryption for data at rest.",
                            "claim_type": "factual",
                            "requirement_refs": ["R1"],
                            "evidence_refs": ["E1"],
                        },
                        {
                            "text": "BidPilot uses AES-256 encryption for data at rest.",
                            "claim_type": "factual",
                            "requirement_refs": ["R9"],
                            "evidence_refs": ["E1"],
                        },
                        {
                            "text": "BidPilot is certified for every global regulation.",
                            "claim_type": "factual",
                            "requirement_refs": ["R1"],
                            "evidence_refs": ["E1"],
                        },
                    ],
                }
            ),
            model_used="test-model",
            provider_type="openai",
            usage=None,
        ),
        draft_markdown=draft,
        requirement_refs={"R1": "requirement-1"},
        evidence_refs={"E1": "chunk-1"},
    )

    assert review["passed"] is True
    assert candidates == [
        {
            "claim_text": "BidPilot uses AES-256 encryption for data at rest.",
            "claim_type": "factual",
            "requirement_ids": ["requirement-1"],
            "evidence_chunk_ids": ["chunk-1"],
        }
    ]


def test_persisted_claim_trace_is_transactional_and_idempotent() -> None:
    suffix = uuid4().hex[:10]
    organization_id = str(uuid4())
    project_id = str(uuid4())
    requirement_id = str(uuid4())
    run_id = str(uuid4())
    db = SessionLocal()
    try:
        organization = Organization(
            id=organization_id,
            slug=f"claim-integrity-{suffix}",
            name="Claim Integrity Test",
        )
        project = Project(
            id=project_id,
            org_id=organization.id,
            slug=f"claim-project-{suffix}",
            name="Claim Integrity Project",
            scenario_package="bidpilot",
        )
        bundle = Bundle(project_id=project.id, label="Claim evidence", source_type="upload")
        db.add_all((organization, project, bundle))
        db.flush()
        source = SourceDocument(
            bundle_id=bundle.id,
            storage_key=f"tests/claim-integrity-{suffix}.md",
            mime_type="text/markdown",
            checksum=uuid4().hex * 2,
            original_filename="claim-integrity.md",
        )
        db.add(source)
        db.flush()
        chunk = KnowledgeChunk(
            project_id=project.id,
            source_document_id=source.id,
            chunk_index=0,
            content="AES-256 encryption protects data at rest.",
        )
        requirement = RequirementItem(
            id=requirement_id,
            project_id=project.id,
            section_key="security",
            requirement_text="Sensitive data must be encrypted at rest.",
            priority="high",
            status="open",
        )
        run = ExecutionRun(
            id=run_id,
            project_id=project.id,
            run_type="draft_section",
            status="running",
        )
        db.add_all((chunk, requirement, run))
        db.flush()
        evidence_set = _add_evidence_set(
            db,
            project_id=project.id,
            run_id=run.id,
            section_key="security",
            source=source,
            chunk=chunk,
        )
        response_plan_state = _add_response_plan_binding(
            db,
            project_id=project.id,
            run_id=run.id,
            evidence_set_id=evidence_set.id,
            section_key="security",
            generation_iteration=1,
        )
        db.commit()
        chunk_id = chunk.id
        source_id = source.id
        evidence_set_id = evidence_set.id
    finally:
        db.close()


    claim_text = "BidPilot uses AES-256 encryption for data at rest."
    state = {
        "project_id": project_id,
        "section_key": "security",
        "run_id": run_id,
        "draft_markdown": claim_text,
        "draft_model_used": "test-model",
        "evidence_set_id": evidence_set_id,
        "evidence_chunks": [
            {
                "chunk_id": chunk_id,
                "source_document_id": source_id,
                "content": "AES-256 encryption protects data at rest.",
                "locator_json": {"chunk_index": 0},
                "chunk_index": 0,
            }
        ],
        "claim_candidates": [
            {
                "claim_text": claim_text,
                "claim_type": "factual",
                "requirement_ids": [requirement_id],
                "evidence_chunk_ids": [chunk_id],
            },
            {
                "claim_text": "An invented statement not present in the final draft.",
                "claim_type": "factual",
                "requirement_ids": [requirement_id],
                "evidence_chunk_ids": [chunk_id],
            },
        ],
        "claim_integrity_status": "proposed",
        "iteration": 1,
        **response_plan_state,
    }

    first = persist_result_node(state)
    second = persist_result_node(state)

    assert first["persisted"] is True
    assert first["claim_count"] == 1
    assert first["claim_integrity_status"] == "proposed"
    assert second["section_version_id"] == first["section_version_id"]
    assert second["claim_count"] == 1

    db = SessionLocal()
    try:
        versions = list(
            db.scalars(select(SectionVersion).where(SectionVersion.generation_run_id == run_id)).all()
        )
        claims = list(
            db.scalars(select(Claim).where(Claim.section_version_id == first["section_version_id"])).all()
        )
        assert len(versions) == 1
        assert versions[0].evidence_set_id == evidence_set_id
        assert versions[0].response_plan_section_id == response_plan_state[
            "response_plan_section_id"
        ]
        assert versions[0].response_plan_evidence_binding_id == response_plan_state[
            "response_plan_evidence_binding_id"
        ]
        assert len(claims) == 1
        claim = claims[0]
        assert claim.claim_text == claim_text
        assert claim.status == "draft"
        assert claim.created_by_actor == "ai"
        requirement_links = list(
            db.scalars(select(RequirementClaimLink).where(RequirementClaimLink.claim_id == claim.id)).all()
        )
        claim_evidence_links = list(
            db.scalars(select(ClaimEvidenceLink).where(ClaimEvidenceLink.claim_id == claim.id)).all()
        )
        requirement_evidence_links = list(
            db.scalars(
                select(RequirementEvidenceLink).where(
                    RequirementEvidenceLink.requirement_id == requirement_id,
                    RequirementEvidenceLink.relation_type == "supports",
                )
            ).all()
        )
        assert [link.requirement_id for link in requirement_links] == [requirement_id]
        assert len(claim_evidence_links) == 1
        assert claim_evidence_links[0].verification_status == "unverified"
        assert len(requirement_evidence_links) == 1
        assert requirement_evidence_links[0].evidence_id == claim_evidence_links[0].evidence_id
        evidence = db.get(Evidence, claim_evidence_links[0].evidence_id)
        assert evidence is not None
        assert evidence.evidence_set_item_id is not None

        run = db.get(ExecutionRun, run_id)
        assert run is not None
        assert run.output_json is not None
        assert run.output_json["claim_count"] == 1
        serialized_output = json.dumps(run.output_json, ensure_ascii=False)
        assert claim_text not in serialized_output
        assert chunk_id not in serialized_output
    finally:
        db.close()


def test_new_worker_draft_reopens_section_without_replacing_approved_snapshot() -> None:
    suffix = uuid4().hex[:10]
    organization_id = str(uuid4())
    project_id = str(uuid4())
    approved_run_id = str(uuid4())
    redraft_run_id = str(uuid4())

    db = SessionLocal()
    try:
        organization = Organization(
            id=organization_id,
            slug=f"approval-snapshot-{suffix}",
            name="Approval Snapshot Test",
        )
        project = Project(
            id=project_id,
            org_id=organization.id,
            slug=f"approval-project-{suffix}",
            name="Approval Snapshot Project",
            scenario_package="bidpilot",
        )
        db.add_all((organization, project))
        db.flush()
        db.add_all(
            (
                ExecutionRun(
                    id=approved_run_id,
                    project_id=project.id,
                    run_type="draft_section",
                    status="running",
                ),
                ExecutionRun(
                    id=redraft_run_id,
                    project_id=project.id,
                    run_type="redraft_section",
                    status="running",
                ),
            )
        )
        db.flush()
        approved_evidence_set = _add_evidence_set(
            db,
            project_id=project.id,
            run_id=approved_run_id,
            section_key="technical",
        )
        redraft_evidence_set = _add_evidence_set(
            db,
            project_id=project.id,
            run_id=redraft_run_id,
            section_key="technical",
        )
        approved_response_plan_state = _add_response_plan_binding(
            db,
            project_id=project.id,
            run_id=approved_run_id,
            evidence_set_id=approved_evidence_set.id,
            section_key="technical",
            generation_iteration=1,
        )
        redraft_response_plan_state = _add_response_plan_binding(
            db,
            project_id=project.id,
            run_id=redraft_run_id,
            evidence_set_id=redraft_evidence_set.id,
            section_key="technical",
            generation_iteration=1,
        )
        db.commit()
        approved_evidence_set_id = approved_evidence_set.id
        redraft_evidence_set_id = redraft_evidence_set.id
    finally:
        db.close()

    approved_result = persist_result_node(
        {
            "project_id": project_id,
            "section_key": "technical",
            "run_id": approved_run_id,
            "draft_markdown": "Approved version one.",
            "draft_model_used": "test-model",
            "evidence_set_id": approved_evidence_set_id,
            "evidence_chunks": [],
            "claim_candidates": [],
            "claim_integrity_status": "not_assessed",
            "iteration": 1,
            "human_decision": "approved",
            **approved_response_plan_state,
        }
    )
    redraft_result = persist_result_node(
        {
            "project_id": project_id,
            "section_key": "technical",
            "run_id": redraft_run_id,
            "draft_markdown": "Unapproved version two.",
            "draft_model_used": "test-model",
            "evidence_set_id": redraft_evidence_set_id,
            "evidence_chunks": [],
            "claim_candidates": [],
            "claim_integrity_status": "not_assessed",
            "iteration": 1,
            "review_passed": True,
            "human_decision": None,
            **redraft_response_plan_state,
        }
    )

    db = SessionLocal()
    try:
        section = db.scalar(
            select(DeliverableSection)
            .join(Deliverable, Deliverable.id == DeliverableSection.deliverable_id)
            .where(
                Deliverable.project_id == project_id,
                DeliverableSection.section_key == "technical",
            )
        )
        assert section is not None
        assert section.status == "in_review"
        assert section.approved_version_id == approved_result["section_version_id"]
        assert redraft_result["section_version_id"] != section.approved_version_id

        deliverable = db.get(Deliverable, section.deliverable_id)
        assert deliverable is not None
        assert deliverable.status == "in_review"
    finally:
        db.close()


def test_review_candidates_are_immutable_per_run_iteration() -> None:
    suffix = uuid4().hex[:10]
    organization_id = str(uuid4())
    project_id = str(uuid4())
    approved_run_id = str(uuid4())
    review_run_id = str(uuid4())

    db = SessionLocal()
    try:
        organization = Organization(
            id=organization_id,
            slug=f"candidate-iterations-{suffix}",
            name="Candidate Iterations Test",
        )
        project = Project(
            id=project_id,
            org_id=organization.id,
            slug=f"candidate-project-{suffix}",
            name="Candidate Iterations Project",
            scenario_package="bidpilot",
        )
        db.add_all((organization, project))
        db.flush()
        db.add_all(
            (
                ExecutionRun(
                    id=approved_run_id,
                    project_id=project.id,
                    run_type="draft_section",
                    status="running",
                ),
                ExecutionRun(
                    id=review_run_id,
                    project_id=project.id,
                    run_type="redraft_section",
                    status="running",
                ),
            )
        )
        db.flush()
        approved_evidence_set = _add_evidence_set(
            db,
            project_id=project.id,
            run_id=approved_run_id,
            section_key="technical",
        )
        review_evidence_set = _add_evidence_set(
            db,
            project_id=project.id,
            run_id=review_run_id,
            section_key="technical",
        )
        approved_response_plan_state = _add_response_plan_binding(
            db,
            project_id=project.id,
            run_id=approved_run_id,
            evidence_set_id=approved_evidence_set.id,
            section_key="technical",
            generation_iteration=1,
        )
        review_response_plan_state = _add_response_plan_binding(
            db,
            project_id=project.id,
            run_id=review_run_id,
            evidence_set_id=review_evidence_set.id,
            section_key="technical",
            generation_iteration=1,
        )
        db.commit()
        approved_evidence_set_id = approved_evidence_set.id
        review_evidence_set_id = review_evidence_set.id
    finally:
        db.close()

    approved = persist_result_node(
        {
            "project_id": project_id,
            "section_key": "technical",
            "run_id": approved_run_id,
            "draft_markdown": "Approved baseline.",
            "draft_model_used": "test-model",
            "evidence_set_id": approved_evidence_set_id,
            "evidence_chunks": [],
            "claim_candidates": [],
            "claim_integrity_status": "not_assessed",
            "iteration": 1,
            "human_decision": "approved",
            **approved_response_plan_state,
        }
    )
    first_candidate = persist_result_node(
        {
            "project_id": project_id,
            "section_key": "technical",
            "run_id": review_run_id,
            "draft_markdown": "Candidate requiring review.",
            "draft_model_used": "test-model",
            "evidence_set_id": review_evidence_set_id,
            "evidence_chunks": [],
            "claim_candidates": [],
            "claim_integrity_status": "not_assessed",
            "iteration": 1,
            "review_passed": True,
            "human_decision": None,
            **review_response_plan_state,
        }
    )
    replayed_candidate = persist_result_node(
        {
            "project_id": project_id,
            "section_key": "technical",
            "run_id": review_run_id,
            "draft_markdown": "Candidate requiring review.",
            "draft_model_used": "test-model",
            "evidence_set_id": review_evidence_set_id,
            "evidence_chunks": [],
            "claim_candidates": [],
            "claim_integrity_status": "not_assessed",
            "iteration": 1,
            "review_passed": True,
            "human_decision": None,
            **review_response_plan_state,
        }
    )
    assert replayed_candidate["section_version_id"] == first_candidate["section_version_id"]

    db = SessionLocal()
    try:
        section = db.scalar(
            select(DeliverableSection)
            .join(Deliverable, Deliverable.id == DeliverableSection.deliverable_id)
            .where(
                Deliverable.project_id == project_id,
                DeliverableSection.section_key == "technical",
            )
        )
        assert section is not None
        assert section.status == "in_review"
        assert section.approved_version_id == approved["section_version_id"]

        first_thread = db.scalar(
            select(ReviewThread).where(ReviewThread.section_version_id == first_candidate["section_version_id"])
        )
        assert first_thread is not None
        assert first_thread.status == "open"
        review_run = db.get(ExecutionRun, review_run_id)
        assert review_run is not None
        assert review_run.status == "awaiting_human"

        # Model the durable API decision before LangGraph re-plans and drafts
        # the next candidate in the same graph run.
        first_thread.status = "rejected"
        review_run.status = "running"
        section.status = "approved"
        second_response_plan_state = _add_response_plan_binding(
            db,
            project_id=project_id,
            run_id=review_run_id,
            evidence_set_id=review_evidence_set_id,
            section_key="technical",
            generation_iteration=2,
        )
        db.commit()
    finally:
        db.close()

    second_candidate = persist_result_node(
        {
            "project_id": project_id,
            "section_key": "technical",
            "run_id": review_run_id,
            "draft_markdown": "Revised candidate requiring review.",
            "draft_model_used": "test-model",
            "evidence_set_id": review_evidence_set_id,
            "evidence_chunks": [],
            "claim_candidates": [],
            "claim_integrity_status": "not_assessed",
            "iteration": 2,
            "review_passed": True,
            "human_decision": None,
            **second_response_plan_state,
        }
    )

    db = SessionLocal()
    try:
        versions = list(
            db.scalars(
                select(SectionVersion)
                .where(SectionVersion.generation_run_id == review_run_id)
                .order_by(SectionVersion.generation_iteration.asc())
            ).all()
        )
        assert [version.generation_iteration for version in versions] == [1, 2]
        assert [version.id for version in versions] == [
            first_candidate["section_version_id"],
            second_candidate["section_version_id"],
        ]

        section = db.scalar(
            select(DeliverableSection)
            .join(Deliverable, Deliverable.id == DeliverableSection.deliverable_id)
            .where(
                Deliverable.project_id == project_id,
                DeliverableSection.section_key == "technical",
            )
        )
        assert section is not None
        assert section.status == "in_review"
        assert section.approved_version_id == approved["section_version_id"]
    finally:
        db.close()
