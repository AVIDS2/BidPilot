from __future__ import annotations

import json as json_module

import pytest

from app.adapters.memory_graph import extract_memory_graph
from app.adapters.provider_errors import ProviderInvocationError
from contracts import MemoryCitation, MemoryGraphEvidenceRef, MemoryGraphEntityProposal, MemoryGraphEntityType, MemoryGraphProposal


class _Response:
    status_code = 200

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def _citation() -> MemoryCitation:
    return MemoryCitation(
        source_type="knowledge_chunk",
        source_id="chunk-1",
        label="技术规范 · 片段 1",
    )


def _proposal(source_id: str = "chunk-1") -> dict:
    return MemoryGraphProposal(
        entities=(
            MemoryGraphEntityProposal(
                local_id="deployment",
                canonical_name="私有化部署",
                entity_type=MemoryGraphEntityType.REQUIREMENT,
                evidence_refs=(MemoryGraphEvidenceRef(source_type="knowledge_chunk", source_id=source_id),),
            ),
        ),
    ).model_dump(mode="json")


def test_openai_graph_extractor_returns_only_validated_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_post(_url, *, headers, json, timeout):
        captured["headers"] = headers
        captured["payload"] = json
        assert timeout == 90.0
        return _Response(
            {
                "choices": [{"message": {"content": json_module.dumps(_proposal())}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
        )

    monkeypatch.setattr("app.adapters.memory_graph.httpx.post", fake_post)

    result = extract_memory_graph(
        title="私有化部署要求",
        body_markdown="投标方案必须说明私有化部署方案。",
        citations=(_citation(),),
        provider_config={
            "provider_type": "openai",
            "provider_id": "custom-openai",
            "api_key": "test-key",
            "api_url": "https://models.example.test/v1",
            "model": "test-model",
        },
    )

    assert result.model_used == "test-model"
    assert result.proposal.entities[0].canonical_name == "私有化部署"
    assert result.usage is not None
    assert result.usage.total_tokens == 15
    assert captured["payload"]["temperature"] == 0
    assert "private" not in captured["payload"]["messages"][0]["content"].lower()


def test_graph_extractor_rejects_model_evidence_outside_authorized_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.adapters.memory_graph.httpx.post",
        lambda *_args, **_kwargs: _Response(
            {
                "choices": [{"message": {"content": json_module.dumps(_proposal("forged-chunk"))}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
        ),
    )

    with pytest.raises(ProviderInvocationError) as error:
        extract_memory_graph(
            title="私有化部署要求",
            body_markdown="投标方案必须说明私有化部署方案。",
            citations=(_citation(),),
            provider_config={
                "provider_type": "openai",
                "provider_id": "custom-openai",
                "api_key": "test-key",
                "api_url": "https://models.example.test/v1",
                "model": "test-model",
            },
        )

    assert error.value.error_code == "provider_response_invalid"
