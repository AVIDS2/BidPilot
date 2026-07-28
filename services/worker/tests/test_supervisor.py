"""Tests for supervisor routing logic."""

from app.graph.nodes.supervisor import (
    supervisor_node,
    route_initial,
    route_after_review,
    route_after_persist,
)
from app.graph.state import BidPilotState


def _make_state(**overrides) -> BidPilotState:
    """Create a test state with defaults."""
    state: BidPilotState = {
        "project_id": "test-project",
        "section_key": "exec-summary",
        "run_id": "test-run",
        "provider_config_id": None,
        "input_review_feedback": None,
        "requirements": [],
        "requirements_parsed": False,
        "memory_context_loaded": True,
        "memory_context_items": [],
        "memory_context_version": None,
        "memory_context_degraded_reasons": [],
        "memory_proposal_ids": [],
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
        "human_decision": None,
        "human_feedback": None,
        "iteration": 0,
        "max_iterations": 3,
        "error": None,
    }
    state.update(overrides)
    return state


class TestRouteInitial:
    def test_no_requirements_goes_to_rfp_parser(self):
        state = _make_state(requirements_parsed=False)
        assert route_initial(state) == "rfp_parser"

    def test_parsed_requirements_without_memory_go_to_memory_context(self):
        state = _make_state(requirements_parsed=True, memory_context_loaded=False)
        assert route_initial(state) == "memory_context"

    def test_no_evidence_goes_to_knowledge_retriever(self):
        state = _make_state(requirements_parsed=True, evidence_retrieved=False)
        assert route_initial(state) == "knowledge_retriever"

    def test_no_content_plan_goes_to_content_plan(self):
        state = _make_state(
            requirements_parsed=True,
            evidence_retrieved=True,
            content_plan_ready=False,
            draft_created=False,
        )
        assert route_initial(state) == "content_plan"

    def test_no_draft_goes_to_section_drafter(self):
        state = _make_state(
            requirements_parsed=True,
            evidence_retrieved=True,
            content_plan_ready=True,
            draft_created=False,
        )
        assert route_initial(state) == "section_drafter"

    def test_no_review_goes_to_quality_reviewer(self):
        state = _make_state(
            requirements_parsed=True, evidence_retrieved=True,
            content_plan_ready=True,
            draft_created=True, review_result=None,
        )
        assert route_initial(state) == "quality_reviewer"

    def test_review_passed_goes_to_persist(self):
        state = _make_state(
            requirements_parsed=True, evidence_retrieved=True,
            content_plan_ready=True,
            draft_created=True, review_result={"passed": True},
            review_passed=True,
        )
        assert route_initial(state) == "human_approval"

    def test_max_iterations_does_not_skip_initial_work(self):
        state = _make_state(iteration=3, max_iterations=3, requirements_parsed=False)
        assert route_initial(state) == "rfp_parser"


class TestRouteAfterReview:
    def test_evidence_boundary_error_ends_workflow_without_persisting(self):
        assert route_after_review(_make_state(error="evidence_set_unavailable")) == "failed"

    def test_review_passed_persists_candidate_before_human_approval(self):
        state = _make_state(review_passed=True)
        assert route_after_review(state) == "persist_result"

    def test_review_failed_iteration_below_max_goes_to_content_plan(self):
        state = _make_state(review_passed=False, iteration=1, max_iterations=3)
        assert route_after_review(state) == "content_plan"

    def test_review_failed_iteration_at_max_goes_to_persist(self):
        state = _make_state(review_passed=False, iteration=3, max_iterations=3)
        assert route_after_review(state) == "persist_result"


class TestRouteAfterPersist:
    def test_review_candidate_goes_to_human_approval_after_persistence(self):
        assert route_after_persist(_make_state(review_passed=True, human_decision=None)) == "human_approval"

    def test_approved_candidate_finishes_after_persistence(self):
        assert route_after_persist(_make_state(review_passed=True, human_decision="approved")) == "memory_proposals"


class TestSupervisorNode:
    def test_preserves_draft_iteration(self):
        state = _make_state(iteration=2)
        result = supervisor_node(state)
        assert result["iteration"] == 2

    def test_handles_error_state(self):
        state = _make_state(error="something went wrong")
        result = supervisor_node(state)
        # Should still return a valid routing decision
        assert "iteration" in result
