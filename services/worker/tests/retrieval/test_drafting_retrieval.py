from types import SimpleNamespace
from unittest.mock import MagicMock

from app.adapters.embedding import EmbeddingResult
from app.execution.drafting import _link_evidence, _retrieve_evidence
from contracts import (
    CitationLocator,
    CitationValidationStatus,
    EmbeddingOutcomeStatus,
    RetrievalCandidate,
    RetrievalResult,
)


def _candidate() -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id="chunk-1",
        project_id="project-1",
        source_document_id="source-1",
        content="云平台部署方案",
        locator=CitationLocator(
            source_document_id="source-1",
            chunk_index=2,
            heading="技术要求",
            text_anchor="云平台部署方案",
            validation_status=CitationValidationStatus.VERIFIED,
        ),
        dense_rank=1,
        sparse_rank=1,
        fused_rank=1,
        final_score=0.04,
        methods=("dense", "fts"),
    )


def test_drafting_retrieves_shared_evidence_candidates(monkeypatch) -> None:
    embedding = EmbeddingResult(
        status=EmbeddingOutcomeStatus.SUCCESS,
        model="qwen/qwen3-embedding-8b",
        profile_id="openrouter:qwen/qwen3-embedding-8b:1536:bidpilot-lexical-v1",
        vector=[0.1] * 1536,
    )
    session = MagicMock()
    expected = RetrievalResult(project_id="project-1", candidates=(_candidate(),))
    session.get.side_effect = [
        SimpleNamespace(id="project-1", org_id="org-1"),
        SimpleNamespace(id="user-1", org_id="org-1", disabled=False),
    ]
    session.scalar.return_value = SimpleNamespace(
        id="runtime-1",
        project_id="project-1",
        org_id="org-1",
        user_id="user-1",
    )
    monkeypatch.setattr(
        "app.execution.drafting.generate_metered_embedding",
        lambda *_args, **_kwargs: embedding,
    )
    monkeypatch.setattr("app.execution.drafting.SessionLocal", lambda: session)
    monkeypatch.setattr(
        "app.execution.drafting.retrieve_project_evidence",
        lambda *_args, **_kwargs: expected,
    )

    candidates = _retrieve_evidence("project-1", "technical-approach", run_id="execution-1")

    assert candidates == expected.candidates
    session.close.assert_called_once()


def test_drafting_evidence_links_keep_locator_without_treating_rank_as_confidence() -> None:
    db = MagicMock()

    _link_evidence(db, "project-1", "section-version-1", (_candidate(),))

    evidence = db.add.call_args.args[0]
    assert evidence.chunk_id == "chunk-1"
    assert evidence.confidence is None
    assert evidence.locator_json == {
        "source_document_id": "source-1",
        "chunk_index": 2,
        "heading": "技术要求",
        "text_anchor": "云平台部署方案",
        "validation_status": "verified",
    }
