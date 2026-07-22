import json
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.auth.schemas import CurrentUser
from app.agent.tools import create_tools
from app.db import SessionLocal
from app.main import app
from app.models import Bundle, KnowledgeChunk, Organization, Project, SourceDocument
from app.retrieval import service as retrieval_service
from app.retrieval.schemas import CitationRead, SearchRequest, SearchResponse, SearchResult
from contracts import (
    CitationLocator,
    CitationValidationStatus,
    EmbeddingOutcome,
    EmbeddingOutcomeStatus,
    RetrievalCandidate,
    RetrievalResult,
    RetrievalTrace,
    normalize_retrieval_text,
)


_EMBEDDING_ENV_NAMES = (
    "EMBEDDING_API_KEY",
    "EMBEDDING_API_URL",
    "EMBEDDING_MODEL",
    "EMBEDDING_DIMENSIONS",
    "DOCPILOT_EMBEDDING_DIMENSIONS",
    "OPENROUTER_API_KEY",
    "OPENROUTER_BASE_URL",
    "OPENROUTER_EMBEDDING_MODEL",
    "OPENROUTER_EMBEDDING_DIMENSIONS",
    "DOCPILOT_PROVIDER_DOMESTIC_API_KEY",
    "DOCPILOT_PROVIDER_DOMESTIC_BASE_URL",
    "DOCPILOT_EMBEDDING_MODEL_TEXT",
    "DOCPILOT_PROVIDER_OPENAI_API_KEY",
    "DOCPILOT_PROVIDER_OPENAI_BASE_URL",
    "OPENAI_API_KEY",
    "ALIYUN_API_KEY",
    "DASHSCOPE_API_KEY",
)


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _disable_embedding_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _EMBEDDING_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def _current_user() -> CurrentUser:
    return CurrentUser(
        id="user-1",
        email="user@example.test",
        display_name="User",
        role="owner",
        org_id="org-1",
        org_slug="org-1",
    )


def test_search_rejects_client_supplied_embedding() -> None:
    client = TestClient(app)

    response = client.post(
        "/retrieval/search",
        json={
            "project_id": "project-1",
            "query": "cloud deployment",
            "embedding": [0.1, 0.2],
        },
    )

    assert response.status_code == 422
    assert "embedding" in response.text


def test_search_authorizes_before_requesting_a_query_embedding(monkeypatch: pytest.MonkeyPatch) -> None:
    embedding_calls: list[str] = []

    def deny_access(*_args, **_kwargs):
        raise HTTPException(status_code=404, detail="Project not found")

    monkeypatch.setattr(retrieval_service, "require_project_capability", deny_access)
    monkeypatch.setattr(
        retrieval_service,
        "generate_metered_query_embedding",
        lambda **kwargs: embedding_calls.append(str(kwargs["query"])),
    )

    with pytest.raises(HTTPException, match="Project not found"):
        retrieval_service.search_command(
            db=object(),
            payload=SearchRequest(project_id="project-1", query="cloud deployment"),
            current_user=_current_user(),
        )

    assert embedding_calls == []


def test_search_maps_safe_hybrid_results_and_reports_degradation(monkeypatch: pytest.MonkeyPatch) -> None:
    candidate = RetrievalCandidate(
        chunk_id="chunk-1",
        project_id="project-1",
        source_document_id="source-1",
        content="投标文件要求支持云平台部署。",
        locator=CitationLocator(
            source_document_id="source-1",
            chunk_index=2,
            heading="技术要求",
            text_anchor="支持云平台部署",
            validation_status=CitationValidationStatus.VERIFIED,
        ),
        sparse_rank=1,
        fused_rank=1,
        final_score=0.032,
        methods=("fts", "trigram"),
    )
    retrieval_result = RetrievalResult(
        project_id="project-1",
        candidates=(candidate,),
        degraded_reasons=("dense_unavailable",),
        trace=RetrievalTrace(
            query_kind="project_evidence",
            fts_candidate_count=1,
            trigram_candidate_count=1,
            fused_candidate_count=1,
            returned_candidate_count=1,
            degraded_reasons=("dense_unavailable",),
        ),
    )
    monkeypatch.setattr(
        retrieval_service,
        "require_project_capability",
        lambda *_args, **_kwargs: SimpleNamespace(project=SimpleNamespace(id="project-1")),
    )
    monkeypatch.setattr(
        retrieval_service,
        "generate_metered_query_embedding",
        lambda **_kwargs: EmbeddingOutcome(
            status=EmbeddingOutcomeStatus.NOT_CONFIGURED,
            error_code="embedding_not_configured",
        ),
    )
    monkeypatch.setattr(
        retrieval_service,
        "retrieve_project_evidence",
        lambda *_args, **_kwargs: retrieval_result,
    )

    response = retrieval_service.search_command(
        db=object(),
        payload=SearchRequest(project_id="project-1", query="云平台部署"),
        current_user=_current_user(),
    )

    assert response.project_id == "project-1"
    assert response.degraded_reasons == ("dense_unavailable",)
    assert response.results[0].methods == ("fts", "trigram")
    assert response.results[0].citation.validation_status is CitationValidationStatus.VERIFIED
    assert "trace" not in response.model_dump()
    assert "profile_id" not in response.model_dump()


def test_agent_semantic_search_uses_the_shared_retrieval_response(monkeypatch: pytest.MonkeyPatch) -> None:
    response = SearchResponse(
        project_id="project-1",
        results=(
            SearchResult(
                chunk_id="chunk-1",
                source_document_id="source-1",
                content="投标文件要求支持云平台部署。",
                score=0.032,
                methods=("fts", "trigram"),
                citation=CitationRead(
                    source_document_id="source-1",
                    chunk_index=2,
                    heading="技术要求",
                    validation_status=CitationValidationStatus.VERIFIED,
                ),
            ),
        ),
        degraded_reasons=("dense_unavailable",),
    )
    calls: list[dict[str, object]] = []

    def fake_search_knowledge(_db, **kwargs):
        calls.append(kwargs)
        return response

    monkeypatch.setattr("app.retrieval.service.search_knowledge", fake_search_knowledge)
    semantic_search = next(
        tool for tool in create_tools(db=object(), user=_current_user()) if tool.name == "semantic_search"
    )

    result = json.loads(semantic_search.invoke({"project_id": "project-1", "query": "云平台部署"}))

    assert calls == [
        {
            "project_id": "project-1",
            "query": "云平台部署",
            "current_user": _current_user(),
        }
    ]
    assert result["count"] == 1
    assert result["results"][0]["citation"]["heading"] == "技术要求"
    assert result["degraded_reasons"] == ["dense_unavailable"]


def test_search_returns_project_scoped_sparse_results_when_embedding_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_embedding_env(monkeypatch)
    db = SessionLocal()
    try:
        default_org_id = "00000000-0000-0000-0000-000000000001"
        if db.get(Organization, default_org_id) is None:
            db.add(Organization(id=default_org_id, slug="default", name="Default Organization"))
            db.commit()

        suffix = _uid()
        project = Project(
            name=f"Search Test {suffix}",
            slug=f"search-test-{suffix}",
            scenario_package="bidpilot",
            org_id=default_org_id,
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        bundle = Bundle(project_id=project.id, label="Test Bundle", source_type="upload")
        db.add(bundle)
        db.commit()
        db.refresh(bundle)

        document = SourceDocument(
            bundle_id=bundle.id,
            storage_key="uploads/test.pdf",
            mime_type="application/pdf",
            checksum=f"checksum-{suffix}",
            original_filename="test.pdf",
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        content = "The system must support cloud deployment on AWS."
        db.add(
            KnowledgeChunk(
                project_id=project.id,
                source_document_id=document.id,
                chunk_index=0,
                content=content,
                retrieval_text=normalize_retrieval_text(content),
                embedding_status="pending",
            )
        )
        db.commit()
        project_id = project.id
    finally:
        db.close()

    client = TestClient(app)
    response = client.post(
        "/retrieval/search",
        json={"project_id": project_id, "query": "cloud deployment", "top_k": 5},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project_id
    assert body["results"][0]["content"] == content
    assert "dense_unavailable" in body["degraded_reasons"]
    assert body["results"][0]["methods"]


def test_search_returns_empty_results_when_no_project_evidence_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    _disable_embedding_env(monkeypatch)
    db = SessionLocal()
    try:
        default_org_id = "00000000-0000-0000-0000-000000000001"
        if db.get(Organization, default_org_id) is None:
            db.add(Organization(id=default_org_id, slug="default", name="Default Organization"))
            db.commit()
        suffix = _uid()
        project = Project(
            name=f"Empty Search {suffix}",
            slug=f"empty-search-{suffix}",
            scenario_package="bidpilot",
            org_id=default_org_id,
        )
        db.add(project)
        db.commit()
        project_id = project.id
    finally:
        db.close()

    client = TestClient(app)
    response = client.post(
        "/retrieval/search",
        json={"project_id": project_id, "query": "nonexistent topic", "top_k": 5},
    )

    assert response.status_code == 200
    assert response.json()["results"] == []
    assert "no_evidence_found" in response.json()["degraded_reasons"]
