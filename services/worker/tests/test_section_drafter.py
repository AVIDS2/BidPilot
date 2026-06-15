from app.adapters.llm import DraftResult
from app.graph.nodes import section_drafter as section_drafter_module
from app.graph.nodes.section_drafter import section_drafter_node


def test_section_drafter_increments_draft_iteration(monkeypatch):
    monkeypatch.setattr(section_drafter_module, "_resolve_provider", lambda _provider_config_id: (None, "openai"))
    monkeypatch.setattr(section_drafter_module, "_load_system_prompt", lambda _project_id: None)
    monkeypatch.setattr(
        section_drafter_module,
        "draft_section_openai",
        lambda *args, **kwargs: DraftResult(
            content_markdown="## Draft\n\nContent",
            evidence_ids=[],
            model_used="stub",
        ),
    )

    result = section_drafter_node(
        {
            "project_id": "project-1",
            "section_key": "exec-summary",
            "provider_config_id": None,
            "input_review_feedback": None,
            "human_feedback": None,
            "evidence_chunks": [],
            "iteration": 1,
        }
    )

    assert result["draft_created"] is True
    assert result["iteration"] == 2
