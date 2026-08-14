"""Skills injection + outline auto-recovery unit tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.runtime.skills import build_skill_prompt_block, select_skill_names


def test_select_skills_for_outline_and_research() -> None:
    assert "bid-outline-first" in select_skill_names("请起草执行摘要全部章节")
    assert "bid-research" in select_skill_names("联网研究一下政策资料")
    block = build_skill_prompt_block("请大纲优先批量起草章节")
    assert "skill:bid-outline-first" in block
    assert "get_project_outline" in block or "section_key" in block


def test_outline_auto_recovery_single_project(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.assistant import tools as tools_mod

    calls: list[str] = []

    def boom(db, user, project_id):
        calls.append(project_id)
        raise ValueError("404: Project not found")

    only = SimpleNamespace(
        id="aaaaaaaa-1111-2222-3333-444444444444",
        name="Only",
        scenario_package="bidpilot",
    )

    def fake_accessible(db, current_user=None):
        return [only]

    def fake_list_sections(db, user, arguments):
        assert arguments["project_id"] == only.id
        return SimpleNamespace(result={"items": []})

    monkeypatch.setenv("DOCPILOT_OUTLINE_AUTO_RECOVERY", "true")
    monkeypatch.setattr(tools_mod, "_get_project_for_user", boom)
    monkeypatch.setattr(tools_mod, "list_accessible_projects", fake_accessible)
    monkeypatch.setattr(tools_mod, "list_sections", fake_list_sections)
    monkeypatch.setattr(
        "app.scenarios.templates.get_sections_for_scenario",
        lambda key: [{"section_key": "exec-summary", "title": "执行摘要"}],
    )

    result = tools_mod.get_project_outline(
        db=object(),  # type: ignore[arg-type]
        user=object(),  # type: ignore[arg-type]
        arguments={"project_id": "not-real"},
    )
    assert result.result["auto_recovered"] is True
    assert result.result["project_id"] == only.id
    assert "自动切换" in result.summary
    assert calls == ["not-real"]


def test_outline_auto_recovery_can_disable(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.assistant import tools as tools_mod

    def boom(db, user, project_id):
        raise ValueError("404: Project not found")

    monkeypatch.setenv("DOCPILOT_OUTLINE_AUTO_RECOVERY", "false")
    monkeypatch.setattr(tools_mod, "_get_project_for_user", boom)
    with pytest.raises(ValueError, match="Project not found"):
        tools_mod.get_project_outline(
            db=object(),  # type: ignore[arg-type]
            user=object(),  # type: ignore[arg-type]
            arguments={"project_id": "not-real"},
        )


def test_skill_index_block_lists_metadata_without_bodies() -> None:
    """Level-1 index exposes name+description, never the full body."""
    from app.runtime.skills import build_skill_index, build_skill_index_block

    index = build_skill_index()
    assert any(s.name == "bid-outline-first" for s in index)
    block = build_skill_index_block()
    assert "AVAILABLE_SKILLS:" in block
    # The index must carry the routing description...
    assert "section_key" in block or "outline" in block
    # ...but not the full procedural body (Level 2 stays lazy).
    assert "get_project_outline" not in block


def test_select_skill_routes_on_description_and_legacy_zh() -> None:
    """New-style skills route on description; legacy packs keep zh triggers."""
    from app.runtime.skills import select_skill_names

    # Legacy Chinese trigger still works for existing packs.
    assert "bid-outline-first" in select_skill_names("请起草执行摘要全部章节")
    # English description keyword route also works.
    assert "bid-outline-first" in select_skill_names("draft a technical response")
    assert "bid-research" in select_skill_names("研究一下竞品")
    assert "bid-research" in select_skill_names("research the market")
    # Unrelated input matches nothing.
    assert select_skill_names("今天天气怎么样") == []
