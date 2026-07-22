from __future__ import annotations

from pathlib import Path

import pytest

from app.evaluation.memory_graph_metrics import (
    MemoryGraphBenchmarkCase,
    MemoryGraphBenchmarkDataset,
    MemoryGraphBenchmarkEntity,
    MemoryGraphBenchmarkRelation,
    MemoryGraphCandidateObservation,
    MemoryGraphEvaluationRun,
    MemoryGraphReviewSummary,
    fixture_fingerprint,
    load_memory_graph_benchmark_dataset,
    load_memory_graph_evaluation_run,
    render_memory_graph_markdown,
    score_memory_graph_run,
)
from contracts import (
    EvaluationCaptureKind,
    EvaluationEvidenceProvenance,
    EvaluationReviewLevel,
    MemoryGraphEvidenceRef,
    MemoryGraphEntityProposal,
    MemoryGraphEntityType,
    MemoryGraphProposal,
    MemoryGraphRelationPredicate,
    MemoryGraphRelationProposal,
)


def _entity(name: str, entity_type: MemoryGraphEntityType) -> MemoryGraphBenchmarkEntity:
    return MemoryGraphBenchmarkEntity(canonical_name=name, entity_type=entity_type)


def _evidence(source_id: str) -> MemoryGraphEvidenceRef:
    return MemoryGraphEvidenceRef(source_type="knowledge_chunk", source_id=source_id)


def _case(case_id: str, *, project_id: str = "project-graph") -> MemoryGraphBenchmarkCase:
    requirement = _entity("私有化部署", MemoryGraphEntityType.REQUIREMENT)
    deliverable = _entity("投标方案", MemoryGraphEntityType.DELIVERABLE)
    return MemoryGraphBenchmarkCase(
        id=case_id,
        org_id="org-graph",
        project_id=project_id,
        memory_record_id=f"record-{case_id}",
        available_evidence_refs=(_evidence("chunk-rfp-3"),),
        expected_entities=(requirement, deliverable),
        expected_relations=(
            MemoryGraphBenchmarkRelation(
                subject=requirement,
                predicate=MemoryGraphRelationPredicate.REQUIRES,
                object=deliverable,
                expected_evidence_refs=(_evidence("chunk-rfp-3"),),
            ),
        ),
    )


def _proposal(*, evidence_source_id: str = "chunk-rfp-3") -> dict[str, object]:
    return MemoryGraphProposal(
        entities=(
            MemoryGraphEntityProposal(
                local_id="requirement",
                canonical_name="私有化部署",
                entity_type=MemoryGraphEntityType.REQUIREMENT,
                evidence_refs=(_evidence(evidence_source_id),),
            ),
            MemoryGraphEntityProposal(
                local_id="deliverable",
                canonical_name="投标方案",
                entity_type=MemoryGraphEntityType.DELIVERABLE,
                evidence_refs=(_evidence(evidence_source_id),),
            ),
        ),
        relations=(
            MemoryGraphRelationProposal(
                subject_local_id="requirement",
                predicate=MemoryGraphRelationPredicate.REQUIRES,
                object_local_id="deliverable",
                evidence_refs=(_evidence(evidence_source_id),),
            ),
        ),
    ).model_dump(mode="json")


def test_memory_graph_proposal_requires_declared_endpoints_and_valid_evidence() -> None:
    proposal = MemoryGraphProposal.model_validate(_proposal())
    proposal.validate_evidence_sources({("knowledge_chunk", "chunk-rfp-3")})

    with pytest.raises(ValueError, match="unavailable evidence"):
        proposal.validate_evidence_sources({("knowledge_chunk", "chunk-other")})

    invalid = _proposal()
    relations = invalid["relations"]
    assert isinstance(relations, list)
    relations[0]["object_local_id"] = "missing"
    with pytest.raises(ValueError, match="endpoints"):
        MemoryGraphProposal.model_validate(invalid)


def test_memory_graph_proposal_rejects_duplicate_canonical_entities() -> None:
    duplicate = _proposal()
    entities = duplicate["entities"]
    assert isinstance(entities, list)
    entities[1]["canonical_name"] = " 私有化部署 "
    entities[1]["entity_type"] = "requirement"
    with pytest.raises(ValueError, match="duplicate canonical"):
        MemoryGraphProposal.model_validate(duplicate)


def test_memory_graph_bench_scores_scope_schema_and_grounding_separately() -> None:
    first = _case("first")
    second = _case("second")
    dataset = MemoryGraphBenchmarkDataset(
        dataset_id="memory-graph-test-v1",
        title="Synthetic graph test",
        dataset_role="development",
        cases=(first, second),
    )
    run = MemoryGraphEvaluationRun(
        dataset_id=dataset.dataset_id,
        fixture_fingerprint=fixture_fingerprint(dataset),
        extractor_policy_version="graph-proposal-v1",
        results=(
            MemoryGraphCandidateObservation(
                case_id=first.id,
                org_id=first.org_id,
                project_id=first.project_id,
                memory_record_id=first.memory_record_id,
                proposal_json=_proposal(),
            ),
            MemoryGraphCandidateObservation(
                case_id=second.id,
                org_id=second.org_id,
                project_id="foreign-project",
                memory_record_id=second.memory_record_id,
                proposal_json=_proposal(),
            ),
        ),
    )

    report = score_memory_graph_run(dataset, run)

    assert report.metrics.scope_isolation_pass_rate == 0.5
    assert report.metrics.schema_validity_rate == 0.5
    assert report.metrics.entity_precision == 1
    assert report.metrics.entity_recall == 0.5
    assert report.metrics.relation_precision == 1
    assert report.metrics.relation_recall == 0.5
    assert report.metrics.evidence_validity_rate == 1
    assert report.metrics.grounded_relation_recall == 0.5


def test_memory_graph_bench_keeps_invalid_evidence_visible_in_metrics() -> None:
    case = _case("invalid-evidence")
    dataset = MemoryGraphBenchmarkDataset(
        dataset_id="memory-graph-invalid-evidence-v1",
        title="Synthetic invalid evidence test",
        dataset_role="development",
        cases=(case,),
    )
    run = MemoryGraphEvaluationRun(
        dataset_id=dataset.dataset_id,
        fixture_fingerprint=fixture_fingerprint(dataset),
        extractor_policy_version="graph-proposal-v1",
        results=(
            MemoryGraphCandidateObservation(
                case_id=case.id,
                org_id=case.org_id,
                project_id=case.project_id,
                memory_record_id=case.memory_record_id,
                proposal_json=_proposal(evidence_source_id="chunk-unavailable"),
            ),
        ),
    )

    report = score_memory_graph_run(dataset, run)

    assert report.metrics.schema_validity_rate == 1
    assert report.metrics.evidence_validity_rate == 0
    assert report.metrics.grounded_relation_recall == 0


def test_memory_graph_bench_records_redacted_capture_metadata_and_review_coverage() -> None:
    case = _case("reviewed-capture")
    dataset = MemoryGraphBenchmarkDataset(
        dataset_id="memory-graph-reviewed-capture-v1",
        title="Synthetic reviewed graph capture",
        dataset_role="development",
        cases=(case,),
    )
    provenance = EvaluationEvidenceProvenance(
        evidence_set_id="memory-graph-dev-set",
        capture_id="memory-graph-dev-capture",
        capture_kind=EvaluationCaptureKind.REVIEWED_SNAPSHOT,
        review_level=EvaluationReviewLevel.SINGLE_REVIEWER,
        evaluator_version="memory-graph-bench-v1",
    )
    run = MemoryGraphEvaluationRun(
        dataset_id=dataset.dataset_id,
        fixture_fingerprint=fixture_fingerprint(dataset),
        extractor_policy_version="graph-proposal-v1",
        git_commit="deadbeef",
        provider="openai-compatible",
        model="controlled-test-model",
        latency_ms=125,
        estimated_cost_usd=0.001,
        provenance=provenance,
        results=(
            MemoryGraphCandidateObservation(
                case_id=case.id,
                org_id=case.org_id,
                project_id=case.project_id,
                memory_record_id=case.memory_record_id,
                proposal_json=_proposal(),
                review_summary=MemoryGraphReviewSummary(
                    accepted_item_count=2,
                    rejected_item_count=1,
                ),
            ),
        ),
    )

    report = score_memory_graph_run(dataset, run)

    assert report.provider == "openai-compatible"
    assert report.model == "controlled-test-model"
    assert report.latency_ms == 125
    assert report.estimated_cost_usd == 0.001
    assert report.provenance == provenance
    assert report.metrics.review_summary_validity_rate == 1
    assert report.metrics.review_decision_coverage_rate == 1
    assert report.metrics.full_review_completion_rate == 1
    assert report.capture_readiness.controlled_capture_ready is True
    assert "Complete enough to establish a baseline" in render_memory_graph_markdown(report)


def test_memory_graph_bench_does_not_treat_an_unattributed_fixture_as_controlled_capture() -> None:
    case = _case("unattributed-capture")
    dataset = MemoryGraphBenchmarkDataset(
        dataset_id="memory-graph-unattributed-capture-v1",
        title="Synthetic untracked graph capture",
        dataset_role="development",
        cases=(case,),
    )
    run = MemoryGraphEvaluationRun(
        dataset_id=dataset.dataset_id,
        fixture_fingerprint=fixture_fingerprint(dataset),
        extractor_policy_version="graph-proposal-v1",
        results=(
            MemoryGraphCandidateObservation(
                case_id=case.id,
                org_id=case.org_id,
                project_id=case.project_id,
                memory_record_id=case.memory_record_id,
                proposal_json=_proposal(),
            ),
        ),
    )

    report = score_memory_graph_run(dataset, run)

    assert report.capture_readiness.controlled_capture_ready is False
    assert "provider is required for a controlled capture" in report.capture_readiness.failures
    assert "every successful proposal requires a valid reviewer summary" in report.capture_readiness.failures
    markdown = render_memory_graph_markdown(report)
    assert "## Controlled Capture Evidence" in markdown
    assert "provider is required for a controlled capture" in markdown


def test_memory_graph_bench_rejects_review_summary_without_a_proposal() -> None:
    with pytest.raises(ValueError, match="review summary requires a proposal"):
        MemoryGraphCandidateObservation(
            case_id="failed-run",
            org_id="org-graph",
            project_id="project-graph",
            memory_record_id="record-failed-run",
            error_code="provider_unavailable",
            review_summary=MemoryGraphReviewSummary(accepted_item_count=0, rejected_item_count=0),
        )


def test_memory_graph_bench_scores_non_object_model_output_as_schema_invalid() -> None:
    case = _case("invalid-shape")
    dataset = MemoryGraphBenchmarkDataset(
        dataset_id="memory-graph-invalid-shape-v1",
        title="Synthetic invalid shape test",
        dataset_role="development",
        cases=(case,),
    )
    run = MemoryGraphEvaluationRun(
        dataset_id=dataset.dataset_id,
        fixture_fingerprint=fixture_fingerprint(dataset),
        extractor_policy_version="graph-proposal-v1",
        results=(
            MemoryGraphCandidateObservation(
                case_id=case.id,
                org_id=case.org_id,
                project_id=case.project_id,
                memory_record_id=case.memory_record_id,
                proposal_json=["not", "a", "graph", "object"],
            ),
        ),
    )

    report = score_memory_graph_run(dataset, run)

    assert report.metrics.scope_isolation_pass_rate == 1
    assert report.metrics.schema_validity_rate == 0
    assert report.metrics.entity_recall == 0


def test_memory_graph_benchmark_fixture_is_versioned_and_valid() -> None:
    fixture_path = (
        Path(__file__).resolve().parents[4]
        / "benchmarks"
        / "bidbench"
        / "v1"
        / "demo-smart-community"
        / "memory-graph-development.json"
    )

    dataset = load_memory_graph_benchmark_dataset(fixture_path)

    assert dataset.dataset_id == "memory-graph-development-v1"
    assert dataset.dataset_role == "development"
    assert len(dataset.cases) == 2


def test_memory_graph_control_fixture_cannot_pass_controlled_capture_gate() -> None:
    fixture_root = (
        Path(__file__).resolve().parents[4]
        / "benchmarks"
        / "bidbench"
        / "v1"
        / "demo-smart-community"
    )
    dataset = load_memory_graph_benchmark_dataset(fixture_root / "memory-graph-development.json")
    run = load_memory_graph_evaluation_run(fixture_root / "candidates" / "memory-graph-control.json")

    report = score_memory_graph_run(dataset, run)

    assert report.metrics.schema_validity_rate == 1
    assert report.metrics.evidence_validity_rate == 1
    assert report.capture_readiness.controlled_capture_ready is False
    assert report.capture_readiness.failures == (
        "control_fixture captures cannot establish a quality baseline",
    )
