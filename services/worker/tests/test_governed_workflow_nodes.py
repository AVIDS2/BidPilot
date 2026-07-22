from types import SimpleNamespace

from app.adapters.provider_errors import ProviderInvocationError
from app.adapters.structured_llm import StructuredModelResult
from app.graph.nodes import quality_reviewer as reviewer_module
from app.graph.nodes import rfp_parser as parser_module
from app.graph.nodes import supervisor as supervisor_module


def test_rfp_parser_records_governed_model_usage(monkeypatch):
    captured: dict = {}
    persisted: list = []

    def begin(**kwargs):
        captured["begin"] = kwargs
        return SimpleNamespace(reservation_key="requirements-call")

    def record_usage(**kwargs):
        captured["usage"] = kwargs

    monkeypatch.setattr(parser_module, "_load_project_source", lambda _project_id: (["must"], "must comply"))
    monkeypatch.setattr(parser_module, "resolve_structured_provider", lambda _config_id: (None, "openai"))
    monkeypatch.setattr(parser_module, "begin_workflow_model_call", begin)
    monkeypatch.setattr(
        parser_module,
        "_extract_via_llm",
        lambda *_args, **_kwargs: (
            [
                {
                    "section_key": "compliance",
                    "requirement_text": "Must comply",
                    "priority": "high",
                }
            ],
            StructuredModelResult(
                content="[]",
                model_used="test-model",
                provider_type="openai",
                usage=None,
            ),
        ),
    )
    monkeypatch.setattr(parser_module, "record_workflow_model_usage", record_usage)
    monkeypatch.setattr(parser_module, "_persist_requirements", lambda _project_id, requirements: persisted.extend(requirements))

    result = parser_module.rfp_parser_node(
        {
            "project_id": "project-1",
            "section_key": "summary",
            "run_id": "run-1",
            "provider_config_id": None,
            "reasoning_effort": "medium",
        }
    )

    assert result["requirements_parsed"] is True
    assert persisted[0]["requirement_text"] == "Must comply"
    assert captured["begin"]["workload"] == "workflow_requirement_extraction"
    assert captured["usage"]["reservation_key"] == "requirements-call"


def test_rfp_parser_uses_safe_deterministic_fallback_after_provider_failure(monkeypatch):
    captured: list[dict] = []
    monkeypatch.setattr(parser_module, "_load_project_source", lambda _project_id: (["must"], "must comply"))
    monkeypatch.setattr(parser_module, "resolve_structured_provider", lambda _config_id: (None, "openai"))
    monkeypatch.setattr(
        parser_module,
        "begin_workflow_model_call",
        lambda **_kwargs: SimpleNamespace(reservation_key="requirements-call"),
    )
    monkeypatch.setattr(
        parser_module,
        "_extract_via_llm",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ProviderInvocationError("provider_timeout", "safe", retryable=True)
        ),
    )
    monkeypatch.setattr(parser_module, "resolve_workflow_model_call_failure", lambda **kwargs: captured.append(kwargs))
    monkeypatch.setattr(parser_module, "_persist_requirements", lambda *_args: None)

    result = parser_module.rfp_parser_node(
        {
            "project_id": "project-1",
            "section_key": "summary",
            "run_id": "run-1",
            "provider_config_id": None,
            "reasoning_effort": None,
        }
    )

    assert result["requirements"][0]["requirement_text"] == "must comply"
    assert captured == [
        {
            "run_id": "run-1",
            "reservation_key": "requirements-call",
            "error_code": "provider_timeout",
        }
    ]
    assert "degraded=provider_timeout" in result["agent_history"][0]["output_summary"]


def test_quality_reviewer_records_governed_model_usage(monkeypatch):
    captured: dict = {}

    def begin(**kwargs):
        captured["begin"] = kwargs
        return SimpleNamespace(reservation_key="review-call")

    def record_usage(**kwargs):
        captured["usage"] = kwargs

    monkeypatch.setattr(reviewer_module, "resolve_structured_provider", lambda _config_id: (None, "openai"))
    monkeypatch.setattr(reviewer_module, "begin_workflow_model_call", begin)
    monkeypatch.setattr(
        reviewer_module,
        "invoke_structured_text",
        lambda **_kwargs: StructuredModelResult(
            content='{"passed": true, "issues": [], "suggestions": [], "overall_score": 0.9}',
            model_used="test-model",
            provider_type="openai",
            usage=None,
        ),
    )
    monkeypatch.setattr(reviewer_module, "record_workflow_model_usage", record_usage)

    result = reviewer_module.quality_reviewer_node(
        {
            "project_id": "project-1",
            "section_key": "summary",
            "run_id": "run-1",
            "provider_config_id": None,
            "reasoning_effort": "medium",
            "iteration": 1,
            "draft_markdown": "A" * 300,
            "requirements": [],
            "evidence_chunks": [],
        }
    )

    assert result["review_passed"] is True
    assert captured["begin"]["workload"] == "workflow_quality_review"
    assert captured["usage"]["reservation_key"] == "review-call"


def test_supervisor_has_no_llm_routing_side_path():
    assert not hasattr(supervisor_module, "_llm_routing_decision")
