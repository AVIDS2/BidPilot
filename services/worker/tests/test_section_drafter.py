from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from tenacity import wait_none

from app.adapters.llm import DraftResult
from app.adapters import llm as llm_module
from app.adapters.provider_errors import ProviderInvocationError
from app.graph.nodes import section_drafter as section_drafter_module
from app.graph.nodes.section_drafter import section_drafter_node
from app.graph.nodes.supervisor import route_after_draft
from app.retrieval.evidence_sets import EvidenceSetItemSnapshot, EvidenceSetSnapshot


def test_draft_prompt_forbids_reasoning_transcript():
    prompt = llm_module._build_prompt("exec-summary", ["evidence"])

    assert llm_module._MAX_DRAFT_OUTPUT_TOKENS == 16_000
    assert "Output only the final markdown section" in prompt
    assert "chain-of-thought" in prompt


def test_deepseek_v4_draft_disables_thinking(monkeypatch):
    captured: dict = {}

    monkeypatch.setattr(llm_module, "_api_key", lambda: "test-key")
    monkeypatch.setattr(llm_module, "_api_url", lambda: "https://api.deepseek.com/v1/chat/completions")
    monkeypatch.setattr(llm_module, "_api_model", lambda: "deepseek-v4-flash")
    monkeypatch.setattr(
        llm_module.httpx,
        "post",
        lambda _url, **kwargs: (
            captured.update(kwargs["json"])
            or SimpleNamespace(
                status_code=200,
                json=lambda: {"choices": [{"message": {"content": "## Draft"}}]},
            )
        ),
    )

    llm_module.draft_section("summary", [], "project-1", reasoning_effort="high")

    assert captured["thinking"] == {"type": "disabled"}
    assert "reasoning_effort" not in captured


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


def test_section_drafter_reloads_authorized_evidence_instead_of_state_payload(monkeypatch):
    session = MagicMock()
    snapshot = EvidenceSetSnapshot(
        id="evidence-set-1",
        status="ready",
        degraded_reasons=(),
        rejected_reasons=(),
        unmet_requirement_ids=(),
        items=(
            EvidenceSetItemSnapshot(
                id="evidence-item-1",
                chunk_id="chunk-1",
                source_document_id="source-1",
                source_document_version=1,
                source_document_checksum="a" * 64,
                quote_text="授权证据内容",
                locator_json={"source_document_id": "source-1", "chunk_index": 0},
                retrieval_rank=1,
                retrieval_score=0.9,
                retrieval_methods=("fts",),
                selected_reason="test",
            ),
        ),
    )
    seen_evidence: list[str] = []

    monkeypatch.setattr(section_drafter_module, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        section_drafter_module,
        "load_authorized_evidence_set",
        lambda *_args, **_kwargs: snapshot,
    )
    monkeypatch.setattr(section_drafter_module, "_resolve_provider", lambda _provider_config_id: (None, "openai"))
    monkeypatch.setattr(section_drafter_module, "_load_system_prompt", lambda _project_id: None)

    def draft_stub(_section_key, evidence_texts, *_args, **_kwargs):
        seen_evidence.extend(evidence_texts)
        return DraftResult(content_markdown="## Draft", evidence_ids=[], model_used="stub")

    monkeypatch.setattr(section_drafter_module, "draft_section_openai", draft_stub)

    result = section_drafter_node(
        {
            "project_id": "project-1",
            "section_key": "exec-summary",
            "run_id": "run-1",
            "provider_config_id": None,
            "input_review_feedback": None,
            "human_feedback": None,
            "evidence_set_id": "evidence-set-1",
            "evidence_chunks": [{"content": "伪造 state 内容"}],
            "iteration": 0,
        }
    )

    assert result["draft_created"] is True
    assert seen_evidence == ["授权证据内容"]
    assert result["evidence_chunks"][0]["evidence_set_item_id"] == "evidence-item-1"
    session.commit.assert_called_once()
    session.close.assert_called_once()


def test_section_drafter_stops_when_authorized_evidence_is_invalidated(monkeypatch):
    session = MagicMock()
    model_called: list[bool] = []
    snapshot = EvidenceSetSnapshot(
        id="evidence-set-1",
        status="invalidated",
        degraded_reasons=(),
        rejected_reasons=("source_document_superseded",),
        unmet_requirement_ids=(),
        items=(),
    )
    monkeypatch.setattr(section_drafter_module, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        section_drafter_module,
        "load_authorized_evidence_set",
        lambda *_args, **_kwargs: snapshot,
    )
    monkeypatch.setattr(
        section_drafter_module,
        "draft_section_openai",
        lambda *_args, **_kwargs: model_called.append(True),
    )

    result = section_drafter_node(
        {
            "project_id": "project-1",
            "section_key": "exec-summary",
            "run_id": "run-1",
            "provider_config_id": None,
            "input_review_feedback": None,
            "human_feedback": None,
            "evidence_set_id": "evidence-set-1",
            "evidence_chunks": [],
            "iteration": 0,
        }
    )

    assert model_called == []
    assert result["draft_created"] is False
    assert result["provider_error_code"] == "evidence_set_unavailable"
    session.commit.assert_called_once()
    session.close.assert_called_once()


def test_section_drafter_retries_only_typed_transient_provider_failures(monkeypatch):
    attempts: list[int] = []
    retries: list[dict] = []
    model_calls: list[dict] = []
    uncertain_reservations: list[dict] = []
    usage_records: list[dict] = []

    monkeypatch.setattr(section_drafter_module, "_resolve_provider", lambda _provider_config_id: (None, "openai"))
    monkeypatch.setattr(section_drafter_module, "_load_system_prompt", lambda _project_id: None)
    monkeypatch.setattr(section_drafter_module._draft_with_retry.retry, "wait", wait_none())
    monkeypatch.setattr(
        section_drafter_module,
        "publish_provider_retry",
        lambda *_args, **kwargs: retries.append(kwargs),
    )
    monkeypatch.setattr(
        section_drafter_module,
        "begin_workflow_model_call",
        lambda **kwargs: model_calls.append(kwargs)
        or SimpleNamespace(reservation_key=f"reservation-{len(model_calls)}"),
    )
    monkeypatch.setattr(
        section_drafter_module,
        "mark_workflow_model_call_uncertain",
        lambda **kwargs: uncertain_reservations.append(kwargs),
    )
    monkeypatch.setattr(
        section_drafter_module,
        "record_workflow_model_usage",
        lambda **kwargs: usage_records.append(kwargs),
    )

    def flaky_draft(*_args, **_kwargs):
        attempts.append(1)
        if len(attempts) < 3:
            raise ProviderInvocationError(
                "provider_timeout",
                "模型服务请求超时，正在按策略重试。",
                retryable=True,
            )
        return DraftResult(content_markdown="## Draft", evidence_ids=[], model_used="test-model")

    monkeypatch.setattr(section_drafter_module, "draft_section_openai", flaky_draft)

    result = section_drafter_node(
        {
            "project_id": "project-1",
            "section_key": "exec-summary",
            "run_id": "workflow-run-1",
            "runtime_run_id": "runtime-1",
            "provider_config_id": None,
            "input_review_feedback": None,
            "human_feedback": None,
            "evidence_chunks": [],
            "iteration": 0,
        }
    )

    assert result["draft_created"] is True
    assert len(attempts) == 3
    assert [retry["next_attempt"] for retry in retries] == [2, 3]
    assert all(retry["error_code"] == "provider_timeout" for retry in retries)
    assert [call["operation_key"] for call in model_calls] == [
        "draft-1-attempt-1",
        "draft-1-attempt-2",
        "draft-1-attempt-3",
    ]
    assert [call["reservation_key"] for call in uncertain_reservations] == [
        "reservation-1",
        "reservation-2",
    ]
    assert usage_records[0]["reservation_key"] == "reservation-3"


def test_section_drafter_reserves_first_attempt_of_later_graph_iteration(monkeypatch):
    model_calls: list[dict] = []
    tracker: dict[str, object] = {}

    monkeypatch.setattr(
        section_drafter_module,
        "begin_workflow_model_call",
        lambda **kwargs: model_calls.append(kwargs)
        or SimpleNamespace(reservation_key="later-iteration"),
    )

    class RetryState:
        attempt_number = 1
        kwargs = {
            "run_id": "workflow-run-1",
            "draft_iteration": 1,
            "attempt_tracker": tracker,
        }

    section_drafter_module._prepare_provider_attempt(RetryState())

    assert tracker == {"attempt": 1, "reservation_key": "later-iteration"}
    assert model_calls == [
        {
            "run_id": "workflow-run-1",
            "workload": "workflow_draft",
            "operation_key": "draft-2-attempt-1",
        }
    ]


def test_section_drafter_does_not_retry_provider_auth_failure(monkeypatch):
    attempts: list[int] = []

    monkeypatch.setattr(section_drafter_module, "_resolve_provider", lambda _provider_config_id: (None, "openai"))
    monkeypatch.setattr(section_drafter_module, "_load_system_prompt", lambda _project_id: None)

    def auth_failure(*_args, **_kwargs):
        attempts.append(1)
        raise ProviderInvocationError(
            "provider_auth_failed",
            "模型服务认证失败，请检查所选模型提供商的配置。",
            retryable=False,
        )

    monkeypatch.setattr(section_drafter_module, "draft_section_openai", auth_failure)

    result = section_drafter_node(
        {
            "project_id": "project-1",
            "section_key": "exec-summary",
            "provider_config_id": None,
            "input_review_feedback": None,
            "human_feedback": None,
            "evidence_chunks": [],
            "iteration": 0,
        }
    )

    assert len(attempts) == 1
    assert result["draft_created"] is False
    assert result["provider_error_code"] == "provider_auth_failed"
    assert route_after_draft({"error": result["error"]}) == "failed"


def test_missing_byok_provider_config_is_a_terminal_error(monkeypatch):
    monkeypatch.setattr(section_drafter_module, "resolve_structured_provider", lambda _config_id: (_ for _ in ()).throw(
        ProviderInvocationError(
            "provider_config_missing",
            "所选模型提供商配置已不可用，请重新选择后再试。",
            retryable=False,
        )
    ))

    with pytest.raises(ProviderInvocationError) as error:
        section_drafter_module._resolve_provider("deleted-config")

    assert error.value.error_code == "provider_config_missing"
    assert error.value.retryable is False


def test_section_drafter_returns_safe_failure_for_deleted_byok_config(monkeypatch):
    attempts: list[bool] = []

    monkeypatch.setattr(section_drafter_module, "resolve_structured_provider", lambda _config_id: (_ for _ in ()).throw(
        ProviderInvocationError(
            "provider_config_missing",
            "所选模型提供商配置已不可用，请重新选择后再试。",
            retryable=False,
        )
    ))
    monkeypatch.setattr(
        section_drafter_module,
        "draft_section_openai",
        lambda *_args, **_kwargs: attempts.append(True),
    )

    result = section_drafter_node(
        {
            "project_id": "project-1",
            "section_key": "exec-summary",
            "provider_config_id": "deleted-config",
            "input_review_feedback": None,
            "human_feedback": None,
            "evidence_chunks": [],
            "iteration": 0,
        }
    )

    assert attempts == []
    assert result["draft_created"] is False
    assert result["provider_error_code"] == "provider_config_missing"
    assert "已不可用" in result["error"]
    assert route_after_draft(result) == "failed"
