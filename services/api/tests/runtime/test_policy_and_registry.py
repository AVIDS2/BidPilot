from __future__ import annotations

import pytest

from app.runtime.policy import evaluate_policy
from app.runtime.registry import format_public_result, get_capability_definition
from contracts.runtime import RuntimePolicyOutcome, RuntimeRiskLevel


@pytest.mark.parametrize(
    ("capability", "risk", "requires_approval_in_risky_only"),
    [
        ("search_projects", RuntimeRiskLevel.READ, False),
        ("list_knowledge_portfolio", RuntimeRiskLevel.READ, False),
        ("get_readiness_summary", RuntimeRiskLevel.READ, False),
        ("create_project", RuntimeRiskLevel.LOW_RISK_WRITE, True),
        ("start_draft_section", RuntimeRiskLevel.COSTING, True),
        ("propose_memory_graph", RuntimeRiskLevel.COSTING, True),
        ("delete_project", RuntimeRiskLevel.DESTRUCTIVE, True),
    ],
)
def test_registry_policy_metadata(
    capability: str,
    risk: RuntimeRiskLevel,
    requires_approval_in_risky_only: bool,
) -> None:
    definition = get_capability_definition(capability)
    decision = evaluate_policy(definition, approval_mode="risky_only")

    assert definition.risk_level is risk
    assert decision.requires_approval is requires_approval_in_risky_only


def test_full_access_keeps_hard_confirmation_for_destructive_actions() -> None:
    create_decision = evaluate_policy(get_capability_definition("create_project"), approval_mode="full_access")
    delete_decision = evaluate_policy(get_capability_definition("delete_project"), approval_mode="full_access")

    assert create_decision.outcome is RuntimePolicyOutcome.ALLOW
    assert delete_decision.outcome is RuntimePolicyOutcome.REQUIRE_APPROVAL
    assert delete_decision.requires_typed_confirmation is True


def test_public_formatter_owns_user_facing_summary() -> None:
    result = format_public_result("search_projects", {"count": 2})

    assert result.summary == "找到 2 个项目。"
    assert "search_projects" not in result.summary
    assert result.payload == {"count": 2}


def test_knowledge_portfolio_formatter_exposes_only_safe_aggregate_fields() -> None:
    result = format_public_result(
        "list_knowledge_portfolio",
        {
            "items": [
                {
                    "project_id": "project-1",
                    "project_name": "投标项目 A",
                    "active_shared_count": 3,
                    "proposed_shared_count": 1,
                    "latest_compilation_status": "succeeded",
                    "body_markdown": "must-not-leak",
                    "citations": [{"label": "must-not-leak"}],
                }
            ]
        },
    )

    assert result.summary == "已检查 1 个可访问项目的知识状态。"
    assert result.payload == {
        "count": 1,
        "projects": [
            {
                "project_id": "project-1",
                "project_name": "投标项目 A",
                "active_shared_count": 3,
                "proposed_shared_count": 1,
                "latest_compilation_status": "succeeded",
            }
        ],
    }


def test_workflow_formatter_exposes_only_safe_run_identifiers() -> None:
    result = format_public_result(
        "start_draft_section",
        {
            "run_id": "execution-run-1",
            "runtime_run_id": "runtime-run-1",
            "provider_api_key": "must-not-leak",
        },
    )

    assert result.summary == "起草工作流已启动。"
    assert result.payload == {"run_id": "execution-run-1", "runtime_run_id": "runtime-run-1"}


def test_memory_graph_formatter_exposes_only_workflow_status() -> None:
    result = format_public_result(
        "propose_memory_graph",
        {
            "run_id": "execution-run-1",
            "runtime_run_id": "runtime-run-1",
            "memory_record_id": "source-memory-id",
            "structured_data_json": {"must_not": "leak"},
            "reused": False,
        },
    )

    assert result.summary == "实体关系提案已启动。"
    assert result.payload == {
        "run_id": "execution-run-1",
        "runtime_run_id": "runtime-run-1",
        "reused": False,
    }


def test_retry_formatter_exposes_only_the_new_attempt_identifiers() -> None:
    result = format_public_result(
        "retry_run",
        {
            "id": "execution-run-2",
            "runtime_run_id": "runtime-run-2",
            "parent_execution_run_id": "execution-run-1",
            "input_json": {"provider_api_key": "must-not-leak"},
        },
    )

    assert result.summary == "已创建新的工作流尝试。"
    assert result.payload == {"run_id": "execution-run-2", "runtime_run_id": "runtime-run-2"}
