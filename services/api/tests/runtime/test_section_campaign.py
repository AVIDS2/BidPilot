"""Unit tests for multi-section campaign capability."""

from __future__ import annotations

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
            "secret": "nope",
        },
    )
    assert "本波处理 2 章" in result.summary
    assert "剩余 3 章" in result.summary
    assert result.payload["processed_count"] == 2
    assert "secret" not in result.payload


def test_run_section_campaign_framework_wave(monkeypatch) -> None:
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

    result = run_section_campaign_tool(
        db=object(),  # type: ignore[arg-type]
        user=object(),  # type: ignore[arg-type]
        arguments={"project_id": "p1", "mode": "framework", "max_sections": 2},
    )
    assert result.tool_name == "run_section_campaign"
    assert result.result["processed_count"] == 2
    assert result.result["remaining_count"] == 1
    assert result.result["written_section_keys"] == ["exec-summary", "solution"]
    assert result.result["remaining_section_keys"] == ["pricing"]
    assert result.result["has_more"] is True
    assert written == ["exec-summary", "solution"]
