from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
import pytest

from app.auth.schemas import CurrentUser
from app.evaluation.assistant_metrics import AssistantBenchCase, AssistantBenchDataset, fixture_fingerprint
from app.evaluation.assistant_runtime_capture import (
    AssistantRuntimeCaptureItem,
    AssistantRuntimeCaptureManifest,
    capture_assistant_runtime_run,
)
from app.runtime.operator_graph import OperatorPlan, build_operator_graph
from app.runtime.service import create_runtime_run
from contracts import EvaluationCaptureKind, EvaluationEvidenceProvenance, EvaluationReviewLevel
from contracts.runtime import RuntimePolicyOutcome


def _user(default_org_id: str, default_user_id: str) -> CurrentUser:
    return CurrentUser(
        id=default_user_id,
        email="dev@docpilot.local",
        display_name="Dev User",
        role="admin",
        org_id=default_org_id,
    )


def _manifest(dataset: AssistantBenchDataset, *, run_id: str) -> AssistantRuntimeCaptureManifest:
    return AssistantRuntimeCaptureManifest(
        dataset_id=dataset.dataset_id,
        fixture_fingerprint=fixture_fingerprint(dataset),
        router_version="langgraph-operator-v1",
        git_commit="a" * 40,
        provider="controlled-provider",
        model="controlled-model",
        provenance=EvaluationEvidenceProvenance(
            evidence_set_id="assistant-runtime-capture",
            capture_id="assistant-runtime-capture-1",
            capture_kind=EvaluationCaptureKind.CURRENT_PIPELINE,
            review_level=EvaluationReviewLevel.TWO_PERSON_REVIEW,
            evaluator_version="assistant-runtime-capture-v1",
            attestation_ref="ci:assistant-runtime-capture-1",
        ),
        captures=(AssistantRuntimeCaptureItem(case_id=dataset.cases[0].id, runtime_run_id=run_id),),
    )


def test_runtime_capture_exports_only_redacted_tool_routing_facts(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    dataset = AssistantBenchDataset(
        dataset_id="assistant-runtime-tool-v1",
        title="Runtime tool capture",
        dataset_role="regression",
        cases=(
            AssistantBenchCase(
                id="open-project-page",
                message="打开项目页面",
                expected_mode="tool_action",
                expected_tool_name="open_page",
                required_argument_keys=("route",),
                expected_policy_outcome=RuntimePolicyOutcome.ALLOW,
                expected_typed_confirmation=False,
            ),
        ),
    )
    user = _user(default_org_id, default_user_id)
    runtime_run = create_runtime_run(
        test_db,
        user,
        kind="assistant_turn",
        engine="langgraph_operator",
        model="controlled-model",
        input_json={"message": "打开项目页面"},
    )
    graph = build_operator_graph(
        test_db,
        user,
        planner=lambda _context: OperatorPlan(
            mode="tool",
            capability_name="open_page",
            arguments={"route": "/projects"},
        ),
        checkpointer=InMemorySaver(),
    )
    graph.invoke(
        {"runtime_run_id": runtime_run.id, "user_message": "打开项目页面", "calls_made": 0},
        config={"configurable": {"thread_id": runtime_run.id}},
    )

    manifest = _manifest(dataset, run_id=runtime_run.id)
    captured = capture_assistant_runtime_run(test_db, dataset, manifest)

    observation = captured.results[0]
    assert observation.mode == "tool_action"
    assert observation.tool_name == "open_page"
    assert observation.argument_keys == ("route",)
    assert observation.policy_outcome is RuntimePolicyOutcome.ALLOW
    assert observation.requires_typed_confirmation is False
    serialized = captured.model_dump_json()
    assert runtime_run.id not in serialized
    assert "/projects" not in serialized
    assert "打开项目页面" not in serialized
    with pytest.raises(ValueError, match="model does not match"):
        capture_assistant_runtime_run(
            test_db,
            dataset,
            manifest.model_copy(update={"model": "different-model"}),
        )


def test_runtime_capture_reads_a_durable_missing_input_plan(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    dataset = AssistantBenchDataset(
        dataset_id="assistant-runtime-needs-input-v1",
        title="Runtime missing input capture",
        dataset_role="regression",
        cases=(
            AssistantBenchCase(
                id="create-project-needs-name",
                message="创建项目",
                expected_mode="needs_input",
                expected_tool_name="create_project",
                expected_missing_fields=("name",),
            ),
        ),
    )
    user = _user(default_org_id, default_user_id)
    runtime_run = create_runtime_run(
        test_db,
        user,
        kind="assistant_turn",
        engine="langgraph_operator",
        model="controlled-model",
        input_json={"message": "创建项目"},
    )
    graph = build_operator_graph(
        test_db,
        user,
        planner=lambda _context: OperatorPlan(
            mode="needs_input",
            capability_name="create_project",
            missing_fields=("name",),
            message="请告诉我项目名称。",
        ),
        checkpointer=InMemorySaver(),
    )
    graph.invoke(
        {"runtime_run_id": runtime_run.id, "user_message": "创建项目", "calls_made": 0},
        config={"configurable": {"thread_id": runtime_run.id}},
    )

    captured = capture_assistant_runtime_run(test_db, dataset, _manifest(dataset, run_id=runtime_run.id))

    observation = captured.results[0]
    assert observation.mode == "needs_input"
    assert observation.tool_name == "create_project"
    assert observation.missing_fields == ("name",)
    assert observation.policy_outcome is None
    assert observation.requires_typed_confirmation is None
