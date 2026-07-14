from app.models import (
    BidRequirementProfile,
    Claim,
    ClaimEvidenceLink,
    RequirementClaimLink,
    RequirementDecision,
    RequirementEvidenceLink,
    RequirementItem,
)


def test_requirement_item_has_shared_provenance_assignment_and_version_fields() -> None:
    columns = RequirementItem.__table__.columns

    assert "source_document_id" in columns
    assert "source_locator_json" in columns
    assert "original_text" in columns
    assert "owner_user_id" in columns
    assert "reviewer_user_id" in columns
    assert "due_at" in columns
    assert "verification_status" in columns
    assert "extraction_confidence" in columns
    assert "lock_version" in columns
    assert "updated_at" in columns
    assert RequirementItem.__mapper__.version_id_col is columns["lock_version"]


def test_bid_requirement_profile_keeps_bid_fields_out_of_shared_requirement() -> None:
    shared_columns = RequirementItem.__table__.columns
    bid_columns = BidRequirementProfile.__table__.columns

    assert "score_weight" not in shared_columns
    assert "coverage_status" not in shared_columns
    assert "score_weight" in bid_columns
    assert "coverage_status" in bid_columns
    assert "evidence_status" in bid_columns
    assert "is_mandatory" in bid_columns
    assert bid_columns["requirement_id"].unique is True


def test_requirement_trace_tables_have_unique_edges() -> None:
    evidence_constraints = {
        constraint.name for constraint in RequirementEvidenceLink.__table__.constraints
    }
    requirement_claim_constraints = {
        constraint.name for constraint in RequirementClaimLink.__table__.constraints
    }
    claim_evidence_constraints = {
        constraint.name for constraint in ClaimEvidenceLink.__table__.constraints
    }

    assert "uq_requirement_evidence_relation" in evidence_constraints
    assert "uq_requirement_claim" in requirement_claim_constraints
    assert "uq_claim_evidence_relation" in claim_evidence_constraints


def test_claim_and_requirement_decision_preserve_provenance() -> None:
    claim_columns = Claim.__table__.columns
    decision_columns = RequirementDecision.__table__.columns

    assert "project_id" in claim_columns
    assert "section_version_id" in claim_columns
    assert "generation_run_id" in claim_columns
    assert "created_by_actor" in claim_columns
    assert "requirement_id" in decision_columns
    assert "decision_type" in decision_columns
    assert "rationale" in decision_columns
    assert "requested_by_user_id" in decision_columns
    assert "approved_by_user_id" in decision_columns
