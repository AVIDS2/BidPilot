import pytest
from pathlib import Path
import uuid

from app.db import SessionLocal
from app.evaluation.retrieval_metrics import (
    RetrievalBenchmarkDataset,
    RetrievalBenchmarkHit,
    RetrievalBenchmarkQuery,
    RetrievalEvaluationRun,
    RetrievalQueryResult,
    RetrievalStrategy,
    compare_retrieval_reports,
    build_retrieval_evaluation_run,
    fixture_fingerprint,
    load_retrieval_benchmark_dataset,
    score_retrieval_run,
)
from app.models import Bundle, KnowledgeChunk, Organization, Project, SourceDocument
from contracts import (
    BidBenchLocator,
    BidBenchSource,
    CitationValidationStatus,
    EvaluationCaptureKind,
    EvaluationEvidenceProvenance,
    EvaluationReviewLevel,
    normalize_retrieval_text,
)
from contracts.retrieval_service import retrieve_project_evidence


def _dataset() -> RetrievalBenchmarkDataset:
    return RetrievalBenchmarkDataset(
        schema_version="1.0",
        dataset_id="retrieval-unit-fixture",
        title="Retrieval unit fixture",
        dataset_role="development",
        sources=(
            BidBenchSource(
                id="rfp",
                path="sources/rfp.md",
                title="RFP",
                source_type="tender",
                sha256="a" * 64,
            ),
            BidBenchSource(
                id="supplier",
                path="sources/supplier.md",
                title="Supplier",
                source_type="supplier_evidence",
                sha256="b" * 64,
            ),
        ),
        queries=(
            RetrievalBenchmarkQuery(
                id="query-security",
                query="需要哪些权限与审计能力？",
                authorized_project_id="project-a",
                relevant_chunk_ids=("chunk-security",),
                expected_locators=(BidBenchLocator(source_id="rfp", section="3.5 权限与安全"),),
                mandatory_evidence=True,
            ),
            RetrievalBenchmarkQuery(
                id="query-service",
                query="质保和故障响应要求是什么？",
                authorized_project_id="project-a",
                relevant_chunk_ids=("chunk-service",),
                expected_locators=(BidBenchLocator(source_id="rfp", section="六、服务要求"),),
            ),
            RetrievalBenchmarkQuery(
                id="query-degraded",
                query="是否支持容器化部署？",
                authorized_project_id="project-a",
                relevant_chunk_ids=("chunk-container",),
                expected_locators=(BidBenchLocator(source_id="rfp", section="四、技术要求"),),
                mandatory_evidence=True,
                required_degraded_reasons=("dense_unavailable",),
            ),
        ),
    )


def _run(dataset: RetrievalBenchmarkDataset) -> RetrievalEvaluationRun:
    return RetrievalEvaluationRun(
        schema_version="1.0",
        dataset_id=dataset.dataset_id,
        fixture_fingerprint=fixture_fingerprint(dataset),
        retrieval_profile_id="openrouter:qwen/qwen3-embedding-8b:1536:bidpilot-lexical-v1",
        strategy=RetrievalStrategy.FUSED,
        candidate_limit=10,
        results=(
            RetrievalQueryResult(
                query_id="query-security",
                hits=(
                    RetrievalBenchmarkHit(
                        chunk_id="chunk-security",
                        project_id="project-a",
                        source_id="rfp",
                        locator=BidBenchLocator(source_id="rfp", section="3.5 权限与安全"),
                        locator_validation_status=CitationValidationStatus.VERIFIED,
                    ),
                ),
            ),
            RetrievalQueryResult(
                query_id="query-service",
                hits=(
                    RetrievalBenchmarkHit(
                        chunk_id="foreign-chunk",
                        project_id="project-b",
                        source_id="supplier",
                        locator=BidBenchLocator(source_id="supplier", section="服务"),
                        locator_validation_status=CitationValidationStatus.VERIFIED,
                    ),
                    RetrievalBenchmarkHit(
                        chunk_id="chunk-service",
                        project_id="project-a",
                        source_id="rfp",
                        locator=BidBenchLocator(source_id="rfp", section="六、服务要求"),
                        locator_validation_status=CitationValidationStatus.VERIFIED,
                    ),
                ),
            ),
            RetrievalQueryResult(
                query_id="query-degraded",
                hits=(
                    RetrievalBenchmarkHit(
                        chunk_id="chunk-container",
                        project_id="project-a",
                        source_id="rfp",
                        locator=BidBenchLocator(source_id="rfp", section="四、技术要求"),
                        locator_validation_status=CitationValidationStatus.PARTIAL,
                    ),
                ),
                degraded_reasons=("dense_unavailable",),
            ),
        ),
    )


def test_retrieval_metrics_score_ranking_locator_scope_and_degraded_modes() -> None:
    dataset = _dataset()
    report = score_retrieval_run(dataset, _run(dataset))

    assert report.metrics.recall_at_1 == pytest.approx(2 / 3)
    assert report.metrics.recall_at_3 == 1
    assert report.metrics.recall_at_5 == 1
    assert report.metrics.recall_at_10 == 1
    assert report.metrics.mean_reciprocal_rank == pytest.approx((1 + 0.5 + 1) / 3)
    assert report.metrics.locator_validity_rate == pytest.approx(2 / 3)
    assert report.metrics.mandatory_evidence_recall == 1
    assert report.metrics.counts.cross_project_hit_count == 1
    assert report.metrics.cross_project_denial_rate == pytest.approx(3 / 4)
    assert report.metrics.degraded_mode_pass_rate == 1


def test_retrieval_metrics_preserve_redacted_evidence_provenance() -> None:
    dataset = _dataset()
    provenance = EvaluationEvidenceProvenance(
        evidence_set_id="release-evidence-1",
        capture_id="retrieval-capture-1",
        capture_kind=EvaluationCaptureKind.CURRENT_PIPELINE,
        review_level=EvaluationReviewLevel.TWO_PERSON_REVIEW,
        evaluator_version="bidpilot-evaluation-v1",
        attestation_ref="ci:build-123",
    )

    report = score_retrieval_run(
        dataset,
        _run(dataset).model_copy(update={"provenance": provenance}),
    )

    assert report.provenance == provenance


def test_retrieval_metrics_reject_missing_or_unknown_query_results() -> None:
    dataset = _dataset()
    run = _run(dataset).model_copy(update={"results": _run(dataset).results[:-1]})

    with pytest.raises(ValueError, match="exactly one result"):
        score_retrieval_run(dataset, run)


def test_retrieval_comparison_is_explicitly_invalid_for_different_profile_or_fixture() -> None:
    dataset = _dataset()
    baseline = score_retrieval_run(dataset, _run(dataset))
    changed_profile = _run(dataset).model_copy(update={"retrieval_profile_id": "different-profile"})
    candidate = score_retrieval_run(dataset, changed_profile)

    comparison = compare_retrieval_reports(baseline, candidate)

    assert comparison.valid is False
    assert "retrieval_profile_id" in comparison.invalid_reasons


def test_retrieval_metrics_reject_a_query_result_from_a_different_vector_profile() -> None:
    dataset = _dataset()
    run = _run(dataset)
    mismatched_result = run.results[0].model_copy(update={"profile_id": "other-profile"})
    mismatched_run = run.model_copy(update={"results": (mismatched_result, *run.results[1:])})

    with pytest.raises(ValueError, match="profile_id"):
        score_retrieval_run(dataset, mismatched_run)


def test_committed_retrieval_development_fixture_has_verified_source_hashes() -> None:
    repository_root = Path(__file__).resolve().parents[4]
    fixture_path = (
        repository_root
        / "benchmarks"
        / "bidbench"
        / "v1"
        / "demo-smart-community"
        / "retrieval-development.json"
    )

    fixture = load_retrieval_benchmark_dataset(fixture_path)

    assert fixture.dataset_id == "demo-smart-community-retrieval-dev"
    assert len(fixture.queries) == 4


def test_retrieval_benchmark_runner_consumes_shared_project_scoped_retrieval() -> None:
    suffix = uuid.uuid4().hex[:8]
    project_id = f"project-{suffix}"
    source_id = f"source-{suffix}"
    dataset = RetrievalBenchmarkDataset(
        schema_version="1.0",
        dataset_id=f"runtime-fixture-{suffix}",
        title="Runtime retrieval fixture",
        dataset_role="development",
        sources=(
            BidBenchSource(
                id="rfp",
                path="sources/rfp.md",
                title="RFP",
                source_type="tender",
                sha256="a" * 64,
            ),
        ),
        queries=(
            RetrievalBenchmarkQuery(
                id="security-query",
                query="权限控制和审计日志要求",
                authorized_project_id=project_id,
                relevant_chunk_ids=(f"security-{suffix}",),
                expected_locators=(BidBenchLocator(source_id="rfp", section="3.5 权限与安全"),),
                mandatory_evidence=True,
                required_degraded_reasons=("dense_unavailable",),
            ),
        ),
    )
    db = SessionLocal()
    try:
        organization = Organization(id=f"org-{suffix}", slug=f"eval-{suffix}", name="Evaluation Test")
        project = Project(
            id=project_id,
            org_id=organization.id,
            name="Evaluation Project",
            slug=f"project-{suffix}",
            scenario_package="bidpilot",
        )
        foreign_project = Project(
            id=f"foreign-{suffix}",
            org_id=organization.id,
            name="Foreign Project",
            slug=f"foreign-{suffix}",
            scenario_package="bidpilot",
        )
        db.add(organization)
        db.commit()
        db.add_all((project, foreign_project))
        db.commit()
        bundle = Bundle(id=f"bundle-{suffix}", project_id=project_id, label="Bundle", source_type="upload")
        foreign_bundle = Bundle(
            id=f"foreign-bundle-{suffix}",
            project_id=foreign_project.id,
            label="Foreign Bundle",
            source_type="upload",
        )
        db.add_all((bundle, foreign_bundle))
        db.commit()
        document = SourceDocument(
            id=source_id,
            bundle_id=bundle.id,
            storage_key="uploads/rfp.md",
            mime_type="text/markdown",
            checksum=f"rfp-{suffix}",
            original_filename="rfp.md",
        )
        foreign_document = SourceDocument(
            id=f"foreign-source-{suffix}",
            bundle_id=foreign_bundle.id,
            storage_key="uploads/foreign.md",
            mime_type="text/markdown",
            checksum=f"foreign-{suffix}",
            original_filename="foreign.md",
        )
        db.add_all((document, foreign_document))
        db.commit()
        content = "支持基于角色的权限控制，并记录操作日志、登录日志和数据访问日志。"
        db.add_all(
            (
                KnowledgeChunk(
                    id=f"security-{suffix}",
                    project_id=project_id,
                    source_document_id=source_id,
                    chunk_index=0,
                    content=content,
                    retrieval_text=normalize_retrieval_text(content),
                    metadata_json={
                        "source_document_id": source_id,
                        "heading_path": ["3.5 权限与安全"],
                    },
                    embedding_status="pending",
                ),
                KnowledgeChunk(
                    id=f"foreign-security-{suffix}",
                    project_id=foreign_project.id,
                    source_document_id=foreign_document.id,
                    chunk_index=0,
                    content=content,
                    retrieval_text=normalize_retrieval_text(content),
                    metadata_json={
                        "source_document_id": foreign_document.id,
                        "heading_path": ["3.5 权限与安全"],
                    },
                    embedding_status="pending",
                ),
            )
        )
        db.commit()

        run = build_retrieval_evaluation_run(
            dataset,
            retriever=lambda query: retrieve_project_evidence(
                db,
                project_id=query.authorized_project_id,
                raw_query=query.query,
                profile_id=None,
                query_embedding=None,
                top_k=5,
            ),
            source_id_by_document_id={source_id: "rfp"},
            retrieval_profile_id="openrouter:qwen/qwen3-embedding-8b:1536:bidpilot-lexical-v1",
            strategy=RetrievalStrategy.SPARSE,
            candidate_limit=5,
        )
        report = score_retrieval_run(dataset, run)
    finally:
        db.rollback()
        db.close()

    assert report.metrics.recall_at_1 == 1
    assert report.metrics.locator_validity_rate == 1
    assert report.metrics.counts.cross_project_hit_count == 0
    assert report.metrics.degraded_mode_pass_rate == 1
