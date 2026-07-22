from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy import select

from app.adapters.structured_llm import StructuredModelResult
from app.db import SessionLocal
from app.graph.nodes.persist_result import persist_result_node
from app.graph.nodes.quality_reviewer import _parse_review
from app.models import (
    Bundle,
    Claim,
    ClaimEvidenceLink,
    ExecutionRun,
    KnowledgeChunk,
    Organization,
    Project,
    RequirementClaimLink,
    RequirementEvidenceLink,
    RequirementItem,
    SectionVersion,
    SourceDocument,
)


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
        db.commit()
        chunk_id = chunk.id
        source_id = source.id
    finally:
        db.close()

    claim_text = "BidPilot uses AES-256 encryption for data at rest."
    state = {
        "project_id": project_id,
        "section_key": "security",
        "run_id": run_id,
        "draft_markdown": claim_text,
        "draft_model_used": "test-model",
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

        run = db.get(ExecutionRun, run_id)
        assert run is not None
        assert run.output_json is not None
        assert run.output_json["claim_count"] == 1
        serialized_output = json.dumps(run.output_json, ensure_ascii=False)
        assert claim_text not in serialized_output
        assert chunk_id not in serialized_output
    finally:
        db.close()
