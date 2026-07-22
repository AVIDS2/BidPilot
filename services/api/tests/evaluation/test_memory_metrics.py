from pathlib import Path

import pytest

from app.evaluation.memory_metrics import (
    MemoryBenchmarkCase,
    MemoryBenchmarkDataset,
    MemoryContextItemObservation,
    MemoryContextObservation,
    MemoryEvaluationRun,
    build_memory_evaluation_run,
    compare_memory_reports,
    fixture_fingerprint,
    load_memory_benchmark_dataset,
    load_memory_evaluation_run,
    score_memory_run,
)
from contracts import (
    EvaluationCaptureKind,
    EvaluationEvidenceProvenance,
    EvaluationReviewLevel,
    MemoryCitation,
    MemoryContextItem,
    MemoryContextPack,
    MemoryKind,
    MemoryScope,
)


def _dataset() -> MemoryBenchmarkDataset:
    return MemoryBenchmarkDataset(
        schema_version="1.0",
        dataset_id="memory-unit-fixture",
        title="Memory unit fixture",
        dataset_role="development",
        cases=(
            MemoryBenchmarkCase(
                id="project-governance",
                query="当前项目有哪些部署约束？",
                org_id="org-a",
                user_id="user-a",
                project_id="project-a",
                expected_record_ids=("project-current",),
                forbidden_record_ids=("project-superseded", "project-deleted", "private-other"),
                max_items=2,
                max_characters=200,
            ),
            MemoryBenchmarkCase(
                id="private-preference",
                query="按我的写作偏好给出答案。",
                org_id="org-a",
                user_id="user-a",
                expected_record_ids=("private-style",),
                forbidden_record_ids=("private-other",),
                max_items=2,
                max_characters=200,
            ),
            MemoryBenchmarkCase(
                id="degraded-lexical",
                query="项目的离线交付要求是什么？",
                org_id="org-a",
                user_id="user-a",
                project_id="project-a",
                expected_record_ids=("project-procedure",),
                forbidden_record_ids=("project-foreign",),
                max_items=2,
                max_characters=200,
                required_degraded_reasons=("dense_unavailable",),
            ),
        ),
    )


def _item(
    record_id: str,
    *,
    scope: MemoryScope = MemoryScope.PROJECT_SHARED,
    owner_user_id: str | None = None,
    citation_count: int = 1,
    content_characters: int = 48,
) -> MemoryContextItemObservation:
    return MemoryContextItemObservation(
        record_id=record_id,
        scope=scope,
        owner_user_id=owner_user_id,
        citation_count=citation_count,
        content_characters=content_characters,
    )


def _run(dataset: MemoryBenchmarkDataset) -> MemoryEvaluationRun:
    return MemoryEvaluationRun(
        schema_version="1.0",
        dataset_id=dataset.dataset_id,
        fixture_fingerprint=fixture_fingerprint(dataset),
        policy_version="bidpilot-memory-policy-v1",
        retrieval_profile_id="openrouter:qwen/qwen3-embedding-8b:1536:bidpilot-lexical-v1",
        results=(
            MemoryContextObservation(
                case_id="project-governance",
                org_id="org-a",
                user_id="user-a",
                project_id="project-a",
                memory_version="memory-project-v1",
                items=(_item("project-current"),),
            ),
            MemoryContextObservation(
                case_id="private-preference",
                org_id="org-a",
                user_id="user-a",
                project_id=None,
                memory_version="memory-private-v1",
                items=(
                    _item(
                        "private-style",
                        scope=MemoryScope.USER_PRIVATE,
                        owner_user_id="user-a",
                    ),
                ),
            ),
            MemoryContextObservation(
                case_id="degraded-lexical",
                org_id="org-a",
                user_id="user-a",
                project_id="project-a",
                memory_version="memory-degraded-v1",
                items=(_item("project-procedure"),),
                degraded_reasons=("dense_unavailable",),
            ),
        ),
    )


def test_memory_metrics_score_recall_isolation_provenance_budget_and_degradation() -> None:
    dataset = _dataset()

    report = score_memory_run(dataset, _run(dataset))

    assert report.metrics.expected_record_recall == 1
    assert report.metrics.isolation_pass_rate == 1
    assert report.metrics.provenance_validity_rate == 1
    assert report.metrics.private_ownership_pass_rate == 1
    assert report.metrics.context_budget_pass_rate == 1
    assert report.metrics.degraded_mode_pass_rate == 1


def test_memory_metrics_preserve_redacted_evidence_provenance() -> None:
    dataset = _dataset()
    provenance = EvaluationEvidenceProvenance(
        evidence_set_id="release-evidence-1",
        capture_id="memory-capture-1",
        capture_kind=EvaluationCaptureKind.CURRENT_PIPELINE,
        review_level=EvaluationReviewLevel.TWO_PERSON_REVIEW,
        evaluator_version="bidpilot-evaluation-v1",
        attestation_ref="ci:build-123",
    )

    report = score_memory_run(
        dataset,
        _run(dataset).model_copy(update={"provenance": provenance}),
    )

    assert report.provenance == provenance


def test_memory_metrics_report_scope_provenance_and_budget_regressions() -> None:
    dataset = _dataset()
    run = _run(dataset)
    bad_first = run.results[0].model_copy(
        update={
            "items": (
                *run.results[0].items,
                _item(
                    "project-deleted",
                    citation_count=0,
                    content_characters=300,
                ),
            ),
        }
    )
    report = score_memory_run(dataset, run.model_copy(update={"results": (bad_first, *run.results[1:])}))

    assert report.metrics.counts.forbidden_record_hit_count == 1
    assert report.metrics.isolation_pass_rate == pytest.approx(2 / 3)
    assert report.metrics.provenance_validity_rate == pytest.approx(3 / 4)
    assert report.metrics.context_budget_pass_rate == pytest.approx(2 / 3)


def test_memory_benchmark_builder_adapts_context_packs_without_persisting_bodies() -> None:
    dataset = _dataset()

    def load_context(case: MemoryBenchmarkCase) -> MemoryContextPack:
        item_by_case = {
            "project-governance": MemoryContextItem(
                record_id="project-current",
                title="部署约束",
                body_markdown="必须支持私有化部署。",
                scope=MemoryScope.PROJECT_SHARED,
                kind=MemoryKind.FACT,
                citations=(
                    MemoryCitation(
                        source_type="knowledge_chunk",
                        source_id="chunk-deployment",
                        label="技术规范第 3 节",
                    ),
                ),
            ),
            "private-preference": MemoryContextItem(
                record_id="private-style",
                title="写作偏好",
                body_markdown="先给结论，再给证据。",
                scope=MemoryScope.USER_PRIVATE,
                kind=MemoryKind.PREFERENCE,
                owner_user_id="user-a",
                citations=(
                    MemoryCitation(
                        source_type="human_decision",
                        source_id="user-a",
                        label="用户明确设置",
                    ),
                ),
            ),
            "degraded-lexical": MemoryContextItem(
                record_id="project-procedure",
                title="离线交付",
                body_markdown="交付包应支持离线部署。",
                scope=MemoryScope.PROJECT_SHARED,
                kind=MemoryKind.PROCEDURE,
                citations=(
                    MemoryCitation(
                        source_type="knowledge_chunk",
                        source_id="chunk-offline",
                        label="交付要求",
                    ),
                ),
            ),
        }
        return MemoryContextPack(
            org_id=case.org_id,
            user_id=case.user_id,
            project_id=case.project_id,
            memory_version=f"memory-{case.id}-v1",
            items=(item_by_case[case.id],),
            degraded_reasons=("dense_unavailable",) if case.id == "degraded-lexical" else (),
        )

    run = build_memory_evaluation_run(
        dataset,
        context_loader=load_context,
        policy_version="bidpilot-memory-policy-v1",
        retrieval_profile_id="openrouter:qwen/qwen3-embedding-8b:1536:bidpilot-lexical-v1",
    )

    assert run.results[0].items[0].model_dump() == {
        "record_id": "project-current",
        "scope": "project_shared",
        "owner_user_id": None,
        "citation_count": 1,
        "content_characters": len("部署约束") + len("必须支持私有化部署。"),
    }
    assert score_memory_run(dataset, run).metrics.expected_record_recall == 1


def test_memory_metrics_reject_context_scope_mismatch_and_invalid_comparison() -> None:
    dataset = _dataset()
    run = _run(dataset)
    wrong_scope = run.results[0].model_copy(update={"project_id": "project-b"})
    with pytest.raises(ValueError, match="project_id"):
        score_memory_run(dataset, run.model_copy(update={"results": (wrong_scope, *run.results[1:])}))

    baseline = score_memory_run(dataset, run)
    changed_policy = run.model_copy(update={"policy_version": "bidpilot-memory-policy-v2"})
    comparison = compare_memory_reports(baseline, score_memory_run(dataset, changed_policy))
    assert comparison.valid is False
    assert "policy_version" in comparison.invalid_reasons


def test_committed_memory_development_fixture_and_captured_run_load(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[4]
    fixture = load_memory_benchmark_dataset(
        repository_root / "benchmarks" / "bidbench" / "v1" / "demo-smart-community" / "memory-development.json"
    )

    assert fixture.dataset_id == "demo-smart-community-memory-dev"
    assert len(fixture.cases) == 4

    run_path = tmp_path / "memory-run.json"
    run_path.write_text(_run(_dataset()).model_dump_json(indent=2), encoding="utf-8")
    assert load_memory_evaluation_run(run_path).dataset_id == "memory-unit-fixture"
