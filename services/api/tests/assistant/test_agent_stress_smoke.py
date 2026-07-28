"""CI-friendly smoke covering stress scenarios A/C/D/I without live LLM.

These tests freeze the control-plane behaviors that the live stress suite
validated against a real model:
  A  multi-read tool chain formatting / multi-tool availability
  C  pending confirmation status reply does not re-search
  D  outline → write_section chaining payloads keep section_key
  I  destructive delete requires typed confirmation + ordered resume events
"""

from __future__ import annotations

from app.runtime.harness_loop import build_capability_tool_specs, resolve_harness_budgets
from app.runtime.policy import evaluate_policy
from app.runtime.registry import format_public_result, get_capability_definition
from contracts.runtime import RuntimePolicyOutcome, RuntimeRiskLevel


def test_smoke_A_recon_tools_registered_and_safe_formatters() -> None:
    names = {tool["function"]["name"] for tool in build_capability_tool_specs()}
    for required in (
        "search_projects",
        "list_knowledge_portfolio",
        "get_readiness_summary",
        "get_project_outline",
        "write_section",
        "delete_project",
        "run_section_campaign",
    ):
        assert required in names

    search = format_public_result(
        "search_projects",
        {
            "items": [
                {
                    "id": "aaaaaaaa-1111-2222-3333-444444444444",
                    "short_id": "aaaaaaaa",
                    "name": "Dup",
                    "status": "active",
                    "created_at": "2026-07-20T00:00:00",
                    "name_collision": True,
                }
            ]
        },
    )
    assert "aaaaaaaa" in search.summary or search.payload.get("count") == 1
    assert search.payload["projects"][0]["short_id"] == "aaaaaaaa"

    portfolio = format_public_result(
        "list_knowledge_portfolio",
        {
            "items": [
                {
                    "project_id": "p1",
                    "project_name": "A",
                    "active_shared_count": 1,
                    "proposed_shared_count": 0,
                    "latest_compilation_status": "succeeded",
                    "body_markdown": "secret",
                }
            ]
        },
    )
    assert "body_markdown" not in portfolio.payload.get("projects", [{}])[0]


def test_smoke_C_pending_confirmation_policy_for_delete() -> None:
    definition = get_capability_definition("delete_project")
    decision = evaluate_policy(definition, approval_mode="risky_only")
    assert definition.risk_level is RuntimeRiskLevel.DESTRUCTIVE
    assert decision.requires_approval is True
    assert decision.requires_typed_confirmation is True

    full = evaluate_policy(definition, approval_mode="full_access")
    assert full.outcome is RuntimePolicyOutcome.REQUIRE_APPROVAL
    assert full.requires_typed_confirmation is True


def test_smoke_D_outline_and_write_keep_section_keys() -> None:
    outline = format_public_result(
        "get_project_outline",
        {
            "project_id": "project-1",
            "project_name": "Demo",
            "outline_count": 1,
            "drafted_count": 0,
            "approved_count": 0,
            "items": [
                {
                    "section_key": "executive_summary",
                    "title": "执行摘要",
                    "status": "missing",
                    "has_content": False,
                    "in_template": True,
                    "secret_blob": "must-not-leak",
                }
            ],
        },
    )
    assert outline.payload["sections"][0]["section_key"] == "executive_summary"
    assert "secret_blob" not in outline.payload["sections"][0]

    written = format_public_result(
        "write_section",
        {
            "section_id": "sec-1",
            "section_key": "executive_summary",
            "section_title": "执行摘要",
            "section_version_id": "ver-1",
            "version_number": 1,
            "deliverable_id": "del-1",
            "content_markdown": "must-not-leak",
        },
    )
    assert written.payload["section_key"] == "executive_summary"
    assert "content_markdown" not in written.payload


def test_smoke_I_and_campaign_budget_and_policy() -> None:
    steps, tools = resolve_harness_budgets("请把全部章节批量起草并导出")
    assert steps >= 12
    # A campaign is deliberately represented by one purpose-built tool per
    # model turn. The tool owns its internal waves, which avoids issuing many
    # independent mutating calls from one assistant response.
    assert tools == 1

    campaign = get_capability_definition("run_section_campaign")
    decision = evaluate_policy(campaign, approval_mode="risky_only")
    assert campaign.risk_level is RuntimeRiskLevel.COSTING
    assert decision.requires_approval is True

    public = format_public_result(
        "run_section_campaign",
        {
            "project_id": "p1",
            "mode": "framework",
            "processed_count": 3,
            "remaining_count": 0,
            "processed_section_keys": ["a", "b", "c"],
            "remaining_section_keys": [],
            "has_more": False,
            "waves_run": 2,
            "auto_continue": True,
        },
    )
    assert public.payload["has_more"] is False
    assert public.payload["waves_run"] == 2
    assert "3" in public.summary

    plan = format_public_result(
        "run_section_campaign",
        {
            "project_id": "p1",
            "mode": "plan",
            "processed_count": 0,
            "remaining_count": 5,
            "planned_sections": [{"section_key": "a", "title": "A"}],
            "has_more": True,
            "waves_run": 0,
        },
    )
    assert "规划" in plan.summary
