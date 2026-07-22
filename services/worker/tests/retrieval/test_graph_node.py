from types import SimpleNamespace
from unittest.mock import MagicMock

from app.adapters.embedding import EmbeddingResult
from app.graph.nodes.knowledge_retriever import knowledge_retriever_node
from contracts import (
    CitationLocator,
    CitationValidationStatus,
    EmbeddingOutcomeStatus,
    RetrievalCandidate,
    RetrievalResult,
)


def test_graph_retriever_maps_shared_result_to_evidence_state(monkeypatch) -> None:
    query_embedding = EmbeddingResult(
        status=EmbeddingOutcomeStatus.SUCCESS,
        model="qwen/qwen3-embedding-8b",
        profile_id="openrouter:qwen/qwen3-embedding-8b:1536:bidpilot-lexical-v1",
        vector=[0.1] * 1536,
    )
    retrieval_result = RetrievalResult(
        project_id="project-1",
        profile_id=query_embedding.profile_id,
        candidates=(
            RetrievalCandidate(
                chunk_id="chunk-1",
                project_id="project-1",
                source_document_id="source-1",
                content="云平台部署方案",
                locator=CitationLocator(
                    source_document_id="source-1",
                    chunk_index=4,
                    heading="技术要求",
                    text_anchor="云平台部署方案",
                    validation_status=CitationValidationStatus.VERIFIED,
                ),
                dense_rank=1,
                sparse_rank=1,
                fused_rank=1,
                final_score=0.04,
                methods=("dense", "fts"),
            ),
        ),
    )
    session = MagicMock()
    session.get.side_effect = [
        SimpleNamespace(id="project-1", org_id="org-1"),
        SimpleNamespace(id="runtime-1", project_id="project-1", org_id="org-1", user_id="user-1"),
        SimpleNamespace(id="user-1", org_id="org-1", disabled=False),
    ]
    monkeypatch.setattr(
        "app.graph.nodes.knowledge_retriever.generate_metered_embedding",
        lambda *_args, **_kwargs: query_embedding,
    )
    monkeypatch.setattr("app.graph.nodes.knowledge_retriever.SessionLocal", lambda: session)
    monkeypatch.setattr(
        "app.graph.nodes.knowledge_retriever.retrieve_project_evidence",
        lambda *_args, **_kwargs: retrieval_result,
    )

    result = knowledge_retriever_node(
        {
            "project_id": "project-1",
            "section_key": "technical-approach",
            "run_id": "execution-1",
            "runtime_run_id": "runtime-1",
        }
    )

    assert result["evidence_retrieved"] is True
    assert result["evidence_chunks"] == [
        {
            "chunk_id": "chunk-1",
            "source_document_id": "source-1",
            "content": "云平台部署方案",
            "retrieval_score": 0.04,
            "retrieval_methods": ["dense", "fts"],
            "locator_json": {
                "source_document_id": "source-1",
                "chunk_index": 4,
                "heading": "技术要求",
                "text_anchor": "云平台部署方案",
                "validation_status": "verified",
            },
            "chunk_index": 4,
        }
    ]
    assert "cosine_distance" not in result["evidence_chunks"][0]
    session.close.assert_called_once()
