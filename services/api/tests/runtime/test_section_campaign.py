"""Unit tests for multi-section campaign capability."""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.assistant.tools import run_section_campaign_tool
from app.runtime.registry import format_public_result, get_capability_definition, missing_required_capability_arguments


def test_campaign_registry_metadata() -> None:
    definition = get_capability_definition("run_section_campaign")
    assert definition.risk_level.value == "costing"
    assert missing_required_capability_arguments("run_section_campaign", {}) == ("project_id",)
    assert missing_required_capability_arguments(
        "run_section_campaign",
        {"project_id": "p1"},
    ) == ()


def test_campaign_public_formatter() -> None:
    result = format_public_result(
        "run_section_campaign",
        {
            "project_id": "p1",
            "mode": "framework",
            "processed_count": 2,
            "remaining_count": 3,
            "processed_section_keys": ["a", "b"],
            "remaining_section_keys": ["c", "d", "e"],
            "written_section_keys": ["a", "b"],
            "started_runtime_run_ids": [],
            "failed": [],
            "has_more": True,
            "sensitive_marker": "nope",
        },
    )
    assert "处理 2 章" in result.summary
    assert "剩余 3 章" in result.summary
    assert result.payload["processed_count"] == 2
    assert "sensitive_marker" not in result.payload


def test_run_section_campaign_framework_auto_continues(monkeypatch) -> None:
    outline_items = [
        {"section_key": "exec-summary", "title": "执行摘要", "has_content": False},
        {"section_key": "solution", "title": "技术方案", "has_content": False},
        {"section_key": "pricing", "title": "报价", "has_content": False},
        {"section_key": "done", "title": "已写", "has_content": True},
    ]
    written: list[str] = []

    def fake_outline(db, user, arguments):
        return SimpleNamespace(
            result={
                "project_id": arguments["project_id"],
                "project_name": "Demo",
                "items": outline_items,
            }
        )

    def fake_write(db, user, arguments):
        written.append(arguments["section_key"])
        return SimpleNamespace(result={"section_key": arguments["section_key"]})

    monkeypatch.setattr("app.assistant.tools.get_project_outline", fake_outline)
    monkeypatch.setattr("app.assistant.tools.write_section_tool", fake_write)

    # Default framework auto_continue should drain all empty sections across waves.
    result = run_section_campaign_tool(
        db=object(),  # type: ignore[arg-type]
        user=object(),  # type: ignore[arg-type]
        arguments={"project_id": "p1", "mode": "framework", "max_sections": 2},
    )
    assert result.tool_name == "run_section_campaign"
    assert result.result["processed_count"] == 3
    assert result.result["remaining_count"] == 0
    assert result.result["has_more"] is False
    assert result.result["waves_run"] >= 2
    assert written == ["exec-summary", "solution", "pricing"]


def test_run_section_campaign_plan_mode(monkeypatch) -> None:
    outline_items = [
        {"section_key": "a", "title": "A", "has_content": False},
        {"section_key": "b", "title": "B", "has_content": False},
    ]

    def fake_outline(db, user, arguments):
        return SimpleNamespace(
            result={"project_id": "p1", "project_name": "Demo", "items": outline_items}
        )

    monkeypatch.setattr("app.assistant.tools.get_project_outline", fake_outline)
    result = run_section_campaign_tool(
        db=object(),  # type: ignore[arg-type]
        user=object(),  # type: ignore[arg-type]
        arguments={"project_id": "p1", "mode": "plan"},
    )
    assert result.result["mode"] == "plan"
    assert result.result["remaining_count"] == 2
    assert result.result["processed_count"] == 0
    assert [item["section_key"] for item in result.result["planned_sections"]] == ["a", "b"]


def test_campaign_failure_never_returns_the_raw_exception(monkeypatch) -> None:
    sensitive_marker = "test-sensitive-marker"
    def fake_outline(db, user, arguments):
        return SimpleNamespace(
            result={
                "project_id": arguments["project_id"],
                "project_name": "Demo",
                "items": [{"section_key": "technical", "title": "技术方案", "has_content": False}],
            }
        )

    def fail_write(*_args, **_kwargs):
        raise RuntimeError(f"Authorization: Bearer {sensitive_marker}")

    monkeypatch.setattr("app.assistant.tools.get_project_outline", fake_outline)
    monkeypatch.setattr("app.assistant.tools.write_section_tool", fail_write)

    result = run_section_campaign_tool(
        db=object(),  # type: ignore[arg-type]
        user=object(),  # type: ignore[arg-type]
        arguments={"project_id": "p1", "mode": "framework"},
    )
    public = format_public_result("run_section_campaign", result.result)

    assert result.result["failed"] == [
        {"section_key": "technical", "error_code": "capability_execution_failed"}
    ]
    assert public.payload["failed"] == result.result["failed"]
    assert sensitive_marker not in json.dumps({"result": result.result, "payload": public.payload})


def test_campaign_public_formatter_drops_raw_failure_details() -> None:
    sensitive_marker = "test-sensitive-marker"
    public = format_public_result(
        "run_section_campaign",
        {
            "project_id": "p1",
            "failed": [
                {
                    "section_key": "technical",
                    "error": f"Authorization: Bearer {sensitive_marker}",
                    "error_code": "not a safe public code",
                }
            ],
        },
    )

    assert public.payload["failed"] == [
        {"section_key": "technical", "error_code": "capability_execution_failed"}
    ]
    assert sensitive_marker not in json.dumps(public.payload)
