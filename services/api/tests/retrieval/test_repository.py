import uuid

from app.db import SessionLocal
from app.models import Bundle, KnowledgeChunk, Organization, Project, SourceDocument
from contracts import RerankOutcome, RerankOutcomeStatus, normalize_retrieval_text
from contracts.retrieval_repository import (
    search_dense_candidates,
    search_fts_candidates,
    search_trigram_candidates,
)
from contracts.retrieval_service import retrieve_project_evidence


PROFILE_ID = "openrouter:qwen/qwen3-embedding-8b:1536:bidpilot-lexical-v1"


def _vector(first: float, second: float) -> list[float]:
    return [first, second] + [0.0] * 1534


def _seed_chunks() -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:8]
    db = SessionLocal()
    try:
        org = Organization(id=f"org-{suffix}", slug=f"retrieval-{suffix}", name="Retrieval Test")
        project = Project(
            id=f"project-{suffix}",
            org_id=org.id,
            name="Retrieval Test",
            slug=f"retrieval-{suffix}",
            scenario_package="bidpilot",
        )
        foreign_project = Project(
            id=f"foreign-{suffix}",
            org_id=org.id,
            name="Foreign Retrieval Test",
            slug=f"foreign-{suffix}",
            scenario_package="bidpilot",
        )
        db.add(org)
        db.commit()
        db.add_all([project, foreign_project])
        db.commit()

        bundle = Bundle(id=f"bundle-{suffix}", project_id=project.id, label="Bundle", source_type="upload")
        foreign_bundle = Bundle(
            id=f"foreign-bundle-{suffix}",
            project_id=foreign_project.id,
            label="Foreign Bundle",
            source_type="upload",
        )
        db.add_all([bundle, foreign_bundle])
        db.commit()

        source = SourceDocument(
            id=f"source-{suffix}",
            bundle_id=bundle.id,
            storage_key="uploads/retrieval.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            checksum=suffix,
            original_filename="retrieval.docx",
        )
        foreign_source = SourceDocument(
            id=f"foreign-source-{suffix}",
            bundle_id=foreign_bundle.id,
            storage_key="uploads/foreign.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            checksum=f"foreign-{suffix}",
            original_filename="foreign.docx",
        )
        db.add_all([source, foreign_source])
        db.commit()

        target = KnowledgeChunk(
            id=f"target-{suffix}",
            project_id=project.id,
            source_document_id=source.id,
            chunk_index=0,
            content="投标文件必须支持云平台部署，并符合 ISO 27001。",
            retrieval_text=normalize_retrieval_text("投标文件必须支持云平台部署，并符合 ISO 27001。"),
            embedding=_vector(1.0, 0.0),
            embedding_profile=PROFILE_ID,
            embedding_status="success",
        )
        distractor = KnowledgeChunk(
            id=f"distractor-{suffix}",
            project_id=project.id,
            source_document_id=source.id,
            chunk_index=1,
            content="项目应提供售后服务和培训计划。",
            retrieval_text=normalize_retrieval_text("项目应提供售后服务和培训计划。"),
            embedding=_vector(0.0, 1.0),
            embedding_profile=PROFILE_ID,
            embedding_status="success",
        )
        foreign = KnowledgeChunk(
            id=f"foreign-chunk-{suffix}",
            project_id=foreign_project.id,
            source_document_id=foreign_source.id,
            chunk_index=0,
            content="云平台部署仅存在于其他项目。",
            retrieval_text=normalize_retrieval_text("云平台部署仅存在于其他项目。"),
            embedding=_vector(1.0, 0.0),
            embedding_profile=PROFILE_ID,
            embedding_status="success",
        )
        db.add_all([target, distractor, foreign])
        db.commit()
        return project.id, target.id
    finally:
        db.close()


def test_shared_candidate_repositories_are_project_scoped_and_find_chinese_phrase() -> None:
    project_id, target_id = _seed_chunks()
    db = SessionLocal()
    try:
        dense = search_dense_candidates(
            db,
            project_id=project_id,
            profile_id=PROFILE_ID,
            query_embedding=_vector(1.0, 0.0),
            top_k=5,
        )
        fts = search_fts_candidates(
            db,
            project_id=project_id,
            normalized_query=normalize_retrieval_text("云平台"),
            top_k=5,
        )
        trigram = search_trigram_candidates(
            db,
            project_id=project_id,
            raw_query="云平台",
            top_k=5,
        )
    finally:
        db.close()

    assert dense[0].chunk_id == target_id
    assert target_id in [candidate.chunk_id for candidate in fts]
    assert target_id in [candidate.chunk_id for candidate in trigram]
    assert all(candidate.project_id == project_id for candidate in (*dense, *fts, *trigram))


def test_shared_hybrid_service_fuses_candidates_and_returns_a_citation_locator() -> None:
    project_id, target_id = _seed_chunks()
    db = SessionLocal()
    try:
        result = retrieve_project_evidence(
            db,
            project_id=project_id,
            raw_query="云平台部署",
            profile_id=PROFILE_ID,
            query_embedding=_vector(1.0, 0.0),
            top_k=5,
        )
    finally:
        db.close()

    assert result.candidates[0].chunk_id == target_id
    assert result.candidates[0].methods == ("dense", "fts", "trigram")
    assert result.candidates[0].locator.source_document_id == result.candidates[0].source_document_id
    assert result.trace is not None
    assert result.trace.dense_candidate_count >= 1
    assert result.trace.fts_candidate_count >= 1
    assert result.trace.trigram_candidate_count >= 1


def test_shared_hybrid_service_uses_explicit_rerank_scores_without_changing_scope() -> None:
    project_id, target_id = _seed_chunks()
    db = SessionLocal()
    observed_chunk_ids: list[str] = []

    def reranker(_query, candidates, _top_k):
        observed_chunk_ids.extend(candidate.chunk_id for candidate in candidates)
        distractor_id = next(candidate.chunk_id for candidate in candidates if candidate.chunk_id != target_id)
        return RerankOutcome(
            status=RerankOutcomeStatus.SUCCESS,
            scores={distractor_id: 0.99, target_id: 0.01},
        )

    try:
        result = retrieve_project_evidence(
            db,
            project_id=project_id,
            raw_query="云平台部署",
            profile_id=PROFILE_ID,
            query_embedding=_vector(1.0, 0.0),
            top_k=2,
            reranker=reranker,
        )
    finally:
        db.close()

    assert target_id in observed_chunk_ids
    assert result.candidates[0].chunk_id != target_id
    assert result.candidates[0].rerank_score == 0.99
    assert "rerank" in result.candidates[0].methods
