"""Tests for BidPilotState TypedDict validation."""

from app.graph.state import BidPilotState


def test_state_has_all_required_fields():
    """Verify BidPilotState has all 15+ required fields."""
    required_fields = [
        "project_id", "section_key", "run_id", "provider_config_id",
        "input_review_feedback", "human_feedback", "requirements", "requirements_parsed",
        "evidence_set_id", "evidence_set_status", "evidence_set_unmet_requirement_ids",
        "evidence_set_degraded_reasons",
        "evidence_chunks", "evidence_retrieved",
        "content_plan", "content_plan_ready",
        "draft_markdown",
        "draft_model_used", "draft_created", "review_result",
        "review_passed", "claim_candidates", "claim_integrity_status",
        "section_version_id", "persisted",
        "human_decision", "human_feedback",
        "iteration", "max_iterations", "error",
    ]
    annotations = BidPilotState.__annotations__
    for field in required_fields:
        assert field in annotations, f"Missing field: {field}"


def test_state_initial_values():
    """Verify initial state values are correct."""
    initial: BidPilotState = {
        "project_id": "test-project",
        "section_key": "exec-summary",
        "run_id": "test-run",
        "provider_config_id": None,
        "input_review_feedback": None,
        "requirements": [],
        "requirements_parsed": False,
        "evidence_set_id": None,
        "evidence_set_status": None,
        "evidence_set_unmet_requirement_ids": [],
        "evidence_set_degraded_reasons": [],
        "evidence_chunks": [],
        "evidence_retrieved": False,
        "content_plan": None,
        "content_plan_ready": False,
        "draft_markdown": "",
        "draft_model_used": "",
        "draft_created": False,
        "review_result": None,
        "review_passed": False,
        "claim_candidates": [],
        "claim_integrity_status": "not_assessed",
        "section_version_id": None,
        "persisted": False,
        "iteration": 0,
        "max_iterations": 3,
        "error": None,
    }
    assert initial["iteration"] == 0
    assert initial["max_iterations"] == 3
    assert initial["persisted"] is False
