from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import subprocess
import sys

import pytest

from contracts import (
    EvaluationCaptureKind,
    EvaluationEvidenceProvenance,
    EvaluationReviewLevel,
)
from app.evaluation.bidbench import BidBenchRunReport
from app.evaluation.assistant_metrics import (
    AssistantCaptureReadiness,
    AssistantEvaluationReport,
    AssistantMetricCounts,
    AssistantMetrics,
)
from app.evaluation.memory_metrics import (
    MemoryEvaluationReport,
    MemoryMetricCounts,
    MemoryMetrics,
)
from app.evaluation.metrics import BidBenchMetrics, BidBenchScoreCounts
from app.evaluation.release_gate import (
    QualityGateMode,
    QualityGatePolicy,
    evaluate_quality_gate,
    render_quality_gate_markdown,
)
from app.evaluation.retrieval_metrics import (
    RetrievalEvaluationReport,
    RetrievalMetricCounts,
    RetrievalMetrics,
    RetrievalStrategy,
)


COMMIT = "a" * 40
GENERATED_AT = datetime.now(UTC)


@pytest.fixture(autouse=True)
def reset_usage_events() -> None:
    """The release gate consumes reports only and must not require PostgreSQL."""
    yield


def _policy() -> QualityGatePolicy:
    return QualityGatePolicy.model_validate(
        {
            "schema_version": "1.1",
            "policy_id": "bidpilot-release-v1",
            "bidbench_thresholds": {
                "min_mandatory_recall": 0.95,
                "min_scored_recall": 0.9,
                "min_source_association_accuracy": 1.0,
                "min_combined_score": 0.9,
                "max_unsupported_claim_rate": 0.0,
            },
            "retrieval_thresholds": {
                "min_recall_at_5": 0.9,
                "min_mean_reciprocal_rank": 0.8,
                "min_locator_validity_rate": 1.0,
                "min_mandatory_evidence_recall": 1.0,
                "min_cross_project_denial_rate": 1.0,
            },
            "memory_thresholds": {
                "min_expected_record_recall": 0.8,
                "min_isolation_pass_rate": 1.0,
                "min_provenance_validity_rate": 1.0,
                "min_private_ownership_pass_rate": 1.0,
                "min_context_budget_pass_rate": 1.0,
            },
            "assistant_thresholds": {
                "min_mode_accuracy": 1.0,
                "min_capability_route_accuracy": 1.0,
                "min_missing_input_accuracy": 1.0,
                "min_required_argument_accuracy": 1.0,
                "min_policy_outcome_accuracy": 1.0,
                "min_typed_confirmation_safety_rate": 1.0,
                "min_project_scope_safety_rate": 1.0,
                "max_unknown_capability_rate": 0.0,
            },
            "allowed_release_dataset_roles": ["regression", "hidden"],
        }
    )


def _provenance(
    *,
    evidence_set_id: str = "release-evidence-1",
    capture_id: str | None = None,
    capture_kind: EvaluationCaptureKind = EvaluationCaptureKind.CURRENT_PIPELINE,
    review_level: EvaluationReviewLevel = EvaluationReviewLevel.TWO_PERSON_REVIEW,
    attestation_ref: str | None = "ci:build-123",
) -> EvaluationEvidenceProvenance:
    return EvaluationEvidenceProvenance(
        evidence_set_id=evidence_set_id,
        capture_id=capture_id or f"{evidence_set_id}-capture",
        capture_kind=capture_kind,
        review_level=review_level,
        evaluator_version="bidpilot-evaluation-v1",
        attestation_ref=attestation_ref,
    )


def _bidbench_report(
    *,
    dataset_role: str = "regression",
    git_commit: str | None = COMMIT,
) -> BidBenchRunReport:
    return BidBenchRunReport(
        formula_version="2.0",
        generated_at=GENERATED_AT,
        input_fingerprint="b" * 64,
        dataset_sha256="c" * 64,
        candidate_sha256="d" * 64,
        source_hashes={"rfp": "e" * 64},
        dataset_id="bid-regression",
        dataset_title="Bid regression fixture",
        dataset_role=dataset_role,
        candidate_id="candidate",
        system_name="bidpilot",
        git_commit=git_commit,
        provider="openrouter",
        model="qwen/qwen3-32b",
        prompt_version="bidpilot-agent-v1",
        run_number=1,
        provenance=_provenance(),
        metrics=BidBenchMetrics(
            counts=BidBenchScoreCounts(
                ground_truth_requirements=2,
                candidate_requirements=2,
                matched_requirements=2,
                mandatory_requirements=1,
                matched_mandatory_requirements=1,
                scored_requirements=1,
                matched_scored_requirements=1,
                correctly_classified_requirements=2,
                correctly_covered_requirements=2,
                expected_evidence_links=1,
                candidate_evidence_links=1,
                true_positive_evidence_links=1,
                accepted_claims=1,
                unsupported_claims=0,
            ),
            requirement_recall=1.0,
            requirement_precision=1.0,
            requirement_f1=1.0,
            mandatory_recall=1.0,
            scored_recall=1.0,
            scored_weight_recall=1.0,
            classification_accuracy=1.0,
            coverage_accuracy=1.0,
            source_association_accuracy=1.0,
            evidence_precision=1.0,
            evidence_recall=1.0,
            evidence_f1=1.0,
            unsupported_claim_rate=0.0,
            claim_grounding_rate=1.0,
            completeness_score=1.0,
            traceability_score=1.0,
            combined_score=1.0,
        ),
    )


def _retrieval_report(
    *,
    dataset_role: str = "regression",
    git_commit: str | None = COMMIT,
    cross_project_denial_rate: float = 1.0,
) -> RetrievalEvaluationReport:
    return RetrievalEvaluationReport(
        generated_at=GENERATED_AT,
        dataset_id="retrieval-regression",
        dataset_role=dataset_role,
        fixture_fingerprint="f" * 64,
        retrieval_profile_id="openrouter:qwen/qwen3-embedding-8b:1536:lexical-v1",
        strategy=RetrievalStrategy.FUSED,
        candidate_limit=10,
        git_commit=git_commit,
        provenance=_provenance(),
        metrics=RetrievalMetrics(
            counts=RetrievalMetricCounts(
                query_count=2,
                returned_hit_count=2,
                relevant_hit_count=2,
                verified_locator_hit_count=2,
                mandatory_query_count=1,
                mandatory_queries_with_evidence=1,
                cross_project_hit_count=0,
                degraded_mode_case_count=0,
                passed_degraded_mode_case_count=0,
            ),
            recall_at_1=1.0,
            recall_at_3=1.0,
            recall_at_5=1.0,
            recall_at_10=1.0,
            mean_reciprocal_rank=1.0,
            locator_validity_rate=1.0,
            mandatory_evidence_recall=1.0,
            cross_project_denial_rate=cross_project_denial_rate,
            degraded_mode_pass_rate=None,
        ),
    )


def _memory_report(*, dataset_role: str = "hidden", git_commit: str | None = COMMIT) -> MemoryEvaluationReport:
    return MemoryEvaluationReport(
        generated_at=GENERATED_AT,
        dataset_id="memory-hidden",
        dataset_role=dataset_role,
        fixture_fingerprint="1" * 64,
        policy_version="memory-policy-v1",
        retrieval_profile_id="openrouter:qwen/qwen3-embedding-8b:1536:lexical-v1",
        git_commit=git_commit,
        provenance=_provenance(),
        metrics=MemoryMetrics(
            counts=MemoryMetricCounts(
                case_count=2,
                expected_record_count=2,
                expected_record_hit_count=2,
                forbidden_record_count=1,
                forbidden_record_hit_count=0,
                returned_item_count=2,
                provenance_valid_item_count=2,
                private_item_count=1,
                private_owner_match_count=1,
                budget_pass_case_count=2,
                degraded_mode_case_count=0,
                passed_degraded_mode_case_count=0,
            ),
            expected_record_recall=1.0,
            isolation_pass_rate=1.0,
            provenance_validity_rate=1.0,
            private_ownership_pass_rate=1.0,
            context_budget_pass_rate=1.0,
            degraded_mode_pass_rate=None,
        ),
    )


def _assistant_report(
    *,
    dataset_role: str = "regression",
    git_commit: str | None = COMMIT,
    provider: str | None = "openrouter",
    model: str | None = "qwen/qwen3-32b",
) -> AssistantEvaluationReport:
    return AssistantEvaluationReport(
        generated_at=GENERATED_AT,
        dataset_id="assistant-regression",
        dataset_role=dataset_role,
        fixture_fingerprint="2" * 64,
        router_version="operator-router-v1",
        git_commit=git_commit,
        provider=provider,
        model=model,
        provenance=_provenance(),
        metrics=AssistantMetrics(
            counts=AssistantMetricCounts(
                case_count=4,
                mode_match_count=4,
                capability_case_count=3,
                capability_route_match_count=3,
                missing_input_case_count=1,
                missing_input_match_count=1,
                required_argument_case_count=3,
                required_argument_match_count=3,
                policy_case_count=3,
                policy_match_count=3,
                typed_confirmation_case_count=1,
                typed_confirmation_safe_count=1,
                project_scope_case_count=2,
                project_scope_safe_count=2,
                unknown_capability_count=0,
            ),
            mode_accuracy=1.0,
            capability_route_accuracy=1.0,
            missing_input_accuracy=1.0,
            required_argument_accuracy=1.0,
            policy_outcome_accuracy=1.0,
            typed_confirmation_safety_rate=1.0,
            project_scope_safety_rate=1.0,
            unknown_capability_rate=0.0,
        ),
        capture_readiness=AssistantCaptureReadiness(controlled_capture_ready=True),
    )


def test_release_gate_accepts_versioned_regression_reports() -> None:
    report = evaluate_quality_gate(
        _policy(),
        bidbench_report=_bidbench_report(),
        retrieval_report=_retrieval_report(),
        memory_report=_memory_report(),
        assistant_report=_assistant_report(),
        mode=QualityGateMode.RELEASE,
        expected_git_commit=COMMIT,
    )

    assert report.passed is True
    assert report.release_eligible is True
    assert report.failures == ()
    assert {item.kind for item in report.inputs} == {"bidbench", "retrieval", "memory", "assistant"}
    assert "Release eligible: `True`" in render_quality_gate_markdown(report)


def _release_gate(
    *,
    bidbench_report: BidBenchRunReport | None = None,
    retrieval_report: RetrievalEvaluationReport | None = None,
    memory_report: MemoryEvaluationReport | None = None,
    assistant_report: AssistantEvaluationReport | None = None,
):
    return evaluate_quality_gate(
        _policy(),
        bidbench_report=bidbench_report or _bidbench_report(),
        retrieval_report=retrieval_report or _retrieval_report(),
        memory_report=memory_report or _memory_report(),
        assistant_report=assistant_report or _assistant_report(),
        mode=QualityGateMode.RELEASE,
        expected_git_commit=COMMIT,
    )


def test_release_gate_requires_traceable_fresh_reviewed_evidence() -> None:
    baseline_bidbench = _bidbench_report()
    baseline_retrieval = _retrieval_report()
    baseline_memory = _memory_report()

    cases = (
        (
            "missing provenance",
            _release_gate(bidbench_report=baseline_bidbench.model_copy(update={"provenance": None})),
            "bidbench.provenance is required",
        ),
        (
            "control fixture",
            _release_gate(
                bidbench_report=baseline_bidbench.model_copy(
                    update={
                        "provenance": _provenance(
                            capture_kind=EvaluationCaptureKind.CONTROL_FIXTURE
                        )
                    }
                )
            ),
            "bidbench.capture_kind=control_fixture is not release-eligible",
        ),
        (
            "single reviewer",
            _release_gate(
                retrieval_report=baseline_retrieval.model_copy(
                    update={
                        "provenance": _provenance(
                            review_level=EvaluationReviewLevel.SINGLE_REVIEWER
                        )
                    }
                )
            ),
            "retrieval.review_level=single_reviewer is below two_person_review",
        ),
        (
            "missing attestation",
            _release_gate(
                memory_report=baseline_memory.model_copy(
                    update={"provenance": _provenance(attestation_ref=None)}
                )
            ),
            "memory.attestation_ref is required",
        ),
        (
            "mismatched evidence set",
            _release_gate(
                memory_report=baseline_memory.model_copy(
                    update={"provenance": _provenance(evidence_set_id="release-evidence-2")}
                )
            ),
            "release evidence reports must share one evidence_set_id",
        ),
        (
            "mismatched capture",
            _release_gate(
                memory_report=baseline_memory.model_copy(
                    update={"provenance": _provenance(capture_id="release-other-capture")}
                )
            ),
            "release evidence reports must share one capture_id",
        ),
        (
            "stale report",
            _release_gate(
                bidbench_report=baseline_bidbench.model_copy(
                    update={"generated_at": datetime.now(UTC) - timedelta(days=8)}
                )
            ),
            "bidbench.report_age_hours=",
        ),
        (
            "missing model metadata",
            _release_gate(
                bidbench_report=baseline_bidbench.model_copy(
                    update={"provider": None, "model": None, "prompt_version": None}
                )
            ),
            "bidbench missing release model metadata: provider, model, prompt_version",
        ),
        (
            "missing assistant model metadata",
            _release_gate(assistant_report=_assistant_report(provider=None, model=None)),
            "assistant missing release model metadata: provider, model",
        ),
    )

    for name, report, expected_failure in cases:
        assert report.passed is False, name
        assert report.release_eligible is False, name
        assert any(expected_failure in failure for failure in report.failures), name


def test_release_gate_rejects_development_data_and_commit_drift() -> None:
    report = evaluate_quality_gate(
        _policy(),
        bidbench_report=_bidbench_report(dataset_role="development"),
        retrieval_report=_retrieval_report(git_commit="b" * 40),
        memory_report=_memory_report(),
        assistant_report=_assistant_report(),
        mode=QualityGateMode.RELEASE,
        expected_git_commit=COMMIT,
    )

    assert report.passed is False
    assert report.release_eligible is False
    assert any("bidbench.dataset_role=development" in failure for failure in report.failures)
    assert any("retrieval.git_commit" in failure for failure in report.failures)


def test_development_gate_still_rejects_safety_metric_regression() -> None:
    report = evaluate_quality_gate(
        _policy(),
        bidbench_report=_bidbench_report(dataset_role="development", git_commit=None),
        retrieval_report=_retrieval_report(
            dataset_role="development",
            git_commit=None,
            cross_project_denial_rate=0.5,
        ),
        memory_report=_memory_report(dataset_role="development", git_commit=None),
        assistant_report=_assistant_report(dataset_role="development", git_commit=None),
        mode=QualityGateMode.DEVELOPMENT,
    )

    assert report.passed is False
    assert report.release_eligible is False
    assert any("retrieval.cross_project_denial_rate" in failure for failure in report.failures)


def test_policy_rejects_a_false_green_without_thresholds() -> None:
    payload = _policy().model_dump(mode="json")
    payload["memory_thresholds"] = {}

    with pytest.raises(ValueError, match="memory_thresholds"):
        QualityGatePolicy.model_validate(payload)

    payload = _policy().model_dump(mode="json")
    payload["assistant_thresholds"] = {}

    with pytest.raises(ValueError, match="assistant_thresholds"):
        QualityGatePolicy.model_validate(payload)


def test_release_policy_cannot_disable_evidence_freshness() -> None:
    payload = _policy().model_dump(mode="json")
    payload["max_report_age_hours"] = None

    with pytest.raises(ValueError):
        QualityGatePolicy.model_validate(payload)


def test_quality_gate_cli_writes_a_release_eligible_artifact(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.json"
    bidbench_path = tmp_path / "bidbench.json"
    retrieval_path = tmp_path / "retrieval.json"
    memory_path = tmp_path / "memory.json"
    assistant_path = tmp_path / "assistant.json"
    output_dir = tmp_path / "output"
    policy_path.write_text(_policy().model_dump_json(), encoding="utf-8")
    bidbench_path.write_text(_bidbench_report().model_dump_json(), encoding="utf-8")
    retrieval_path.write_text(_retrieval_report().model_dump_json(), encoding="utf-8")
    memory_path.write_text(_memory_report().model_dump_json(), encoding="utf-8")
    assistant_path.write_text(_assistant_report().model_dump_json(), encoding="utf-8")

    repository_root = Path(__file__).resolve().parents[4]
    result = subprocess.run(
        [
            sys.executable,
            str(repository_root / "scripts" / "run_quality_gate.py"),
            "--policy",
            str(policy_path),
            "--bidbench-report",
            str(bidbench_path),
            "--retrieval-report",
            str(retrieval_path),
            "--memory-report",
            str(memory_path),
            "--assistant-report",
            str(assistant_path),
            "--mode",
            "release",
            "--expected-git-commit",
            COMMIT,
            "--output-dir",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Release eligible: True" in result.stdout
    artifacts = list(output_dir.rglob("quality-gate.json"))
    assert len(artifacts) == 1


def test_release_gate_rejects_assistant_confirmation_regression() -> None:
    assistant = _assistant_report()
    report = _release_gate(
        assistant_report=assistant.model_copy(
            update={
                "metrics": assistant.metrics.model_copy(
                    update={"typed_confirmation_safety_rate": 0.5}
                )
            }
        )
    )

    assert report.passed is False
    assert any("assistant.typed_confirmation_safety_rate=0.5000" in failure for failure in report.failures)
