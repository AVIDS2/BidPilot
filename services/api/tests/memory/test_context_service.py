from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.auth.schemas import CurrentUser
from app.main import app
from app.memory import service as memory_service
from app.memory.schemas import MemoryContextRequest
from contracts import EmbeddingOutcome, EmbeddingOutcomeStatus, MemoryContextPack


def _current_user() -> CurrentUser:
    return CurrentUser(
        id="memory-context-user",
        email="memory-context@example.test",
        display_name="Memory Context",
        role="owner",
        org_id="memory-context-org",
        org_slug="memory-context",
    )


def test_context_rejects_client_supplied_embedding() -> None:
    client = TestClient(app)

    response = client.post(
        "/memory/context",
        json={
            "project_id": "project-memory",
            "query": "部署约束",
            "embedding": [0.1, 0.2],
        },
    )

    assert response.status_code == 422
    assert "embedding" in response.text


def test_context_authorizes_before_requesting_query_embedding(monkeypatch: pytest.MonkeyPatch) -> None:
    embedding_calls: list[str] = []

    def deny_access(*_args, **_kwargs):
        raise HTTPException(status_code=404, detail="Project not found")

    monkeypatch.setattr(memory_service, "require_project_capability", deny_access)
    monkeypatch.setattr(
        "app.retrieval.metered_embedding.generate_metered_query_embedding",
        lambda **kwargs: embedding_calls.append(str(kwargs["query"])),
    )

    with pytest.raises(HTTPException, match="Project not found"):
        memory_service.memory_context_query(
            db=object(),
            payload=MemoryContextRequest(project_id="project-memory", query="部署约束"),
            current_user=_current_user(),
        )

    assert embedding_calls == []


def test_context_maps_server_side_embedding_and_safe_pack(monkeypatch: pytest.MonkeyPatch) -> None:
    expected_pack = MemoryContextPack(
        org_id="memory-context-org",
        user_id="memory-context-user",
        project_id="project-memory",
        memory_version="version-1",
        items=(),
        degraded_reasons=("no_memory_found",),
    )
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        memory_service,
        "require_project_capability",
        lambda *_args, **_kwargs: SimpleNamespace(project=SimpleNamespace(id="project-memory")),
    )
    monkeypatch.setattr(
        "app.retrieval.metered_embedding.generate_metered_query_embedding",
        lambda **_kwargs: EmbeddingOutcome(
            status=EmbeddingOutcomeStatus.NOT_CONFIGURED,
            error_code="embedding_not_configured",
        ),
    )
    monkeypatch.setattr(memory_service, "has_visible_memory", lambda *_args, **_kwargs: True)

    def fake_build(_db, **kwargs):
        calls.append(kwargs)
        return expected_pack

    monkeypatch.setattr(memory_service, "build_memory_context_pack", fake_build)

    response = memory_service.memory_context_query(
        db=object(),
        payload=MemoryContextRequest(project_id="project-memory", query="部署约束"),
        current_user=_current_user(),
    )

    assert response.memory_version == "version-1"
    assert response.degraded_reasons == ("no_memory_found",)
    assert calls == [
        {
            "org_id": "memory-context-org",
            "user_id": "memory-context-user",
            "project_id": "project-memory",
            "raw_query": "部署约束",
            "profile_id": None,
            "query_embedding": None,
            "top_k": 8,
            "max_characters": 12000,
        }
    ]


def test_agent_context_skips_embedding_provider_when_no_memory_is_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_pack = MemoryContextPack(
        org_id="memory-context-org",
        user_id="memory-context-user",
        project_id=None,
        memory_version="version-empty",
        items=(),
        degraded_reasons=("dense_unavailable", "no_memory_found"),
    )
    monkeypatch.setattr(memory_service, "has_visible_memory", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        "app.retrieval.metered_embedding.generate_metered_query_embedding",
        lambda *_args, **_kwargs: pytest.fail("empty memory context must not call an embedding provider"),
    )
    monkeypatch.setattr(memory_service, "build_memory_context_pack", lambda *_args, **_kwargs: expected_pack)

    response = memory_service.memory_context_for_agent(
        db=object(),
        current_user=_current_user(),
        project_id=None,
        query="延续上一轮要求",
    )

    assert response.memory_version == "version-empty"
    assert response.items == ()


def test_agent_context_uses_a_bounded_embedding_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    expected_pack = MemoryContextPack(
        org_id="memory-context-org",
        user_id="memory-context-user",
        project_id=None,
        memory_version="version-memory",
        items=(),
        degraded_reasons=("dense_unavailable", "no_memory_found"),
    )
    captured_timeout: list[float] = []
    monkeypatch.delenv("DOCPILOT_AGENT_MEMORY_EMBEDDING_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setattr(memory_service, "has_visible_memory", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        "app.retrieval.metered_embedding.generate_metered_query_embedding",
        lambda **kwargs: (
            captured_timeout.append(float(kwargs["timeout_seconds"]))
            or EmbeddingOutcome(
                status=EmbeddingOutcomeStatus.NOT_CONFIGURED,
                error_code="embedding_not_configured",
            )
        ),
    )
    monkeypatch.setattr(memory_service, "build_memory_context_pack", lambda *_args, **_kwargs: expected_pack)

    memory_service.memory_context_for_agent(
        db=object(),
        current_user=_current_user(),
        project_id=None,
        query="延续上一轮要求",
    )

    assert captured_timeout == [2.5]
