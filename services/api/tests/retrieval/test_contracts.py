import pytest
from pydantic import ValidationError

from contracts.retrieval import (
    CitationLocator,
    CitationValidationStatus,
    EmbeddingOutcome,
    EmbeddingOutcomeStatus,
    RetrievalCandidate,
    RetrievalProfile,
    RetrievalResult,
    reciprocal_rank_fusion,
)


def _profile() -> RetrievalProfile:
    return RetrievalProfile(
        provider="openrouter",
        model="qwen/qwen3-embedding-8b",
        dimensions=1536,
        normalizer_version="bidpilot-lexical-v1",
    )


def _candidate(*, chunk_id: str = "chunk-1", project_id: str = "project-1") -> RetrievalCandidate:
    return RetrievalCandidate(
        chunk_id=chunk_id,
        project_id=project_id,
        source_document_id="source-1",
        content="投标文件要求提供云平台部署方案。",
        locator=CitationLocator(
            source_document_id="source-1",
            chunk_index=0,
            heading="技术要求",
            text_anchor="云平台部署方案",
            validation_status=CitationValidationStatus.VERIFIED,
        ),
        dense_rank=1,
        sparse_rank=2,
        fused_rank=1,
        final_score=0.0325,
        methods=("dense", "fts"),
    )


def test_retrieval_profile_has_a_stable_identifier() -> None:
    profile = _profile()

    assert profile.identifier == "openrouter:qwen/qwen3-embedding-8b:1536:bidpilot-lexical-v1"


def test_successful_embedding_outcome_requires_a_real_vector() -> None:
    profile = _profile()

    outcome = EmbeddingOutcome(
        status=EmbeddingOutcomeStatus.SUCCESS,
        profile_id=profile.identifier,
        vector=[0.1] * profile.dimensions,
    )

    assert outcome.is_success is True

    with pytest.raises(ValidationError, match="successful embedding requires a vector"):
        EmbeddingOutcome(
            status=EmbeddingOutcomeStatus.SUCCESS,
            profile_id=profile.identifier,
        )


def test_failed_embedding_outcome_cannot_carry_a_zero_vector() -> None:
    with pytest.raises(ValidationError, match="non-successful embedding outcome cannot carry a vector"):
        EmbeddingOutcome(
            status=EmbeddingOutcomeStatus.TRANSIENT_FAILURE,
            error_code="provider_timeout",
            vector=[0.0] * 1536,
        )


def test_retrieval_candidate_rejects_mismatched_locator_source() -> None:
    with pytest.raises(ValidationError, match="locator source_document_id must match"):
        RetrievalCandidate(
            chunk_id="chunk-1",
            project_id="project-1",
            source_document_id="source-1",
            content="内容",
            locator=CitationLocator(
                source_document_id="source-2",
                chunk_index=0,
                validation_status=CitationValidationStatus.PARTIAL,
            ),
            fused_rank=1,
            final_score=0.01,
            methods=("fts",),
        )


def test_retrieval_result_rejects_foreign_project_candidates_and_duplicates() -> None:
    with pytest.raises(ValidationError, match="candidate project_id must match"):
        RetrievalResult(
            project_id="project-1",
            candidates=[_candidate(project_id="project-2")],
        )

    with pytest.raises(ValidationError, match="duplicate chunk_id"):
        RetrievalResult(
            project_id="project-1",
            candidates=[_candidate(), _candidate()],
        )


def test_reciprocal_rank_fusion_rewards_cross_retriever_agreement_deterministically() -> None:
    fused = reciprocal_rank_fusion(
        {
            "dense": ["chunk-1", "chunk-2"],
            "fts": ["chunk-2", "chunk-3"],
        }
    )

    assert [candidate.chunk_id for candidate in fused] == ["chunk-2", "chunk-1", "chunk-3"]
    assert fused[0].method_ranks == {"dense": 2, "fts": 1}
    assert fused[0].score > fused[1].score
