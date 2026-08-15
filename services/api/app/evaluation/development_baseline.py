"""One reproducible, development-only baseline across BidPilot evaluators.

This module intentionally runs no provider and touches no tenant data. Its
control fixtures prove that the four reporting contracts remain connected and
traceable; they are not a model-quality or release claim.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.assistant.schemas import AssistantIntent
from contracts import (
    CitationValidationStatus,
    EvaluationCaptureKind,
    EvaluationEvidenceProvenance,
    EvaluationReviewLevel,
    MemoryScope,
)

from .assistant_metrics import (
    AssistantEvaluationReport,
    build_deterministic_assistant_run,
    load_assistant_benchmark_dataset,
    score_assistant_run,
    write_assistant_report,
)
from .bidbench import BidBenchRunReport, evaluate_files, write_report as write_bidbench_report
from .memory_metrics import (
    MemoryContextItemObservation,
    MemoryContextObservation,
    MemoryEvaluationReport,
    MemoryEvaluationRun,
    fixture_fingerprint as memory_fixture_fingerprint,
    load_memory_benchmark_dataset,
    score_memory_run,
    write_memory_report,
)
from .retrieval_metrics import (
    RetrievalBenchmarkHit,
    RetrievalEvaluationReport,
    RetrievalEvaluationRun,
    RetrievalQueryResult,
    RetrievalStrategy,
    fixture_fingerprint as retrieval_fixture_fingerprint,
    load_retrieval_benchmark_dataset,
    score_retrieval_run,
    write_retrieval_report,
)


DEVELOPMENT_BASELINE_ID = "bidpilot-development-baseline-v1"
MIN_DEVELOPMENT_BASELINE_CASES = 20
_BASELINE_VERSION = "bidpilot-development-baseline-v1"
_NOT_APPLICABLE = "not_applicable"


class _BaselineModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class BaselineReportReceipt(_BaselineModel):
    kind: Literal["bidbench", "retrieval", "memory", "assistant"]
    dataset_id: str = Field(min_length=1, max_length=100)
    dataset_role: str = Field(min_length=1, max_length=30)
    dataset_fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    report_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    case_count: int = Field(ge=1)
    git_commit: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=255)
    capture_kind: EvaluationCaptureKind
    review_level: EvaluationReviewLevel
    controlled_capture_ready: bool | None = None


class DevelopmentBaselineReceipt(_BaselineModel):
    schema_version: Literal["1.0"] = "1.0"
    baseline_id: str = DEVELOPMENT_BASELINE_ID
    generated_at: datetime
    git_commit: str = Field(min_length=1, max_length=100)
    minimum_case_count: int = Field(default=MIN_DEVELOPMENT_BASELINE_CASES, ge=1)
    total_case_count: int = Field(ge=1)
    reports: tuple[BaselineReportReceipt, ...] = Field(min_length=4)
    input_fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    release_eligible: Literal[False] = False
    limitations: tuple[str, ...]

    @model_validator(mode="after")
    def validate_complete_control_suite(self) -> DevelopmentBaselineReceipt:
        kinds = tuple(item.kind for item in self.reports)
        expected_kinds = {"bidbench", "retrieval", "memory", "assistant"}
        if set(kinds) != expected_kinds or len(kinds) != len(expected_kinds):
            raise ValueError("development baseline requires exactly one report for each evaluator")
        if self.total_case_count != sum(item.case_count for item in self.reports):
            raise ValueError("development baseline total_case_count must match report case counts")
        if self.total_case_count < self.minimum_case_count:
            raise ValueError("development baseline does not meet the fixed-case minimum")
        if self.release_eligible:
            raise ValueError("development control baseline can never be release eligible")
        return self


@dataclass(frozen=True)
class DevelopmentBaselineResult:
    receipt: DevelopmentBaselineReceipt
    bidbench_report: BidBenchRunReport
    retrieval_report: RetrievalEvaluationReport
    memory_report: MemoryEvaluationReport
    assistant_report: AssistantEvaluationReport


def build_development_baseline(
    benchmark_root: Path,
    *,
    git_commit: str,
) -> DevelopmentBaselineResult:
    """Evaluate all four contracts with explicit control fixtures.

    The result is deliberately diagnostic only. A reviewed current-pipeline or
    model capture must be produced separately before a release gate can pass.
    """

    commit = git_commit.strip()
    if not commit:
        raise ValueError("git_commit is required for a development baseline")
    root = benchmark_root.resolve()

    bidbench_report = _build_bidbench_control(root, commit)
    retrieval_report = _build_retrieval_control(root, commit)
    memory_report = _build_memory_control(root, commit)
    assistant_report = _build_assistant_control(root, commit)
    reports = (
        _bidbench_receipt(bidbench_report),
        _retrieval_receipt(retrieval_report),
        _memory_receipt(memory_report),
        _assistant_receipt(assistant_report),
    )
    input_fingerprint = _canonical_sha256(
        {
            "baseline_id": DEVELOPMENT_BASELINE_ID,
            "git_commit": commit,
            "reports": [item.model_dump(mode="json") for item in reports],
        }
    )
    receipt = DevelopmentBaselineReceipt(
        generated_at=datetime.now(UTC),
        git_commit=commit,
        total_case_count=sum(item.case_count for item in reports),
        reports=reports,
        input_fingerprint=input_fingerprint,
        limitations=(
            "All inputs are versioned development control fixtures; this is not a production accuracy claim.",
            "The run makes no provider call and includes no tenant or customer document content.",
            "Release promotion still requires reviewed regression or hidden captures under the quality-gate policy.",
        ),
    )
    return DevelopmentBaselineResult(
        receipt=receipt,
        bidbench_report=bidbench_report,
        retrieval_report=retrieval_report,
        memory_report=memory_report,
        assistant_report=assistant_report,
    )


def write_development_baseline(
    result: DevelopmentBaselineResult,
    output_root: Path,
) -> dict[str, Path]:
    """Write all report artifacts and one aggregate receipt under a safe root."""

    root = (output_root.resolve() / result.receipt.baseline_id / result.receipt.git_commit[:12]).resolve()
    output_root_resolved = output_root.resolve()
    if not root.is_relative_to(output_root_resolved):
        raise ValueError("development baseline output path escapes output root")

    bidbench_json, bidbench_markdown = write_bidbench_report(result.bidbench_report, root / "bidbench")
    retrieval_json, retrieval_markdown = write_retrieval_report(result.retrieval_report, root / "retrieval")
    memory_json, memory_markdown = write_memory_report(result.memory_report, root / "memory")
    assistant_json, assistant_markdown = write_assistant_report(result.assistant_report, root / "assistant")
    receipt_json = root / "baseline.json"
    receipt_markdown = root / "baseline.md"
    receipt_json.write_text(result.receipt.model_dump_json(indent=2), encoding="utf-8")
    receipt_markdown.write_text(render_development_baseline_markdown(result.receipt), encoding="utf-8")
    return {
        "bidbench_json": bidbench_json,
        "bidbench_markdown": bidbench_markdown,
        "retrieval_json": retrieval_json,
        "retrieval_markdown": retrieval_markdown,
        "memory_json": memory_json,
        "memory_markdown": memory_markdown,
        "assistant_json": assistant_json,
        "assistant_markdown": assistant_markdown,
        "baseline_json": receipt_json,
        "baseline_markdown": receipt_markdown,
    }


def render_development_baseline_markdown(receipt: DevelopmentBaselineReceipt) -> str:
    lines = [
        "# BidPilot Development Evaluation Baseline",
        "",
        f"- Baseline: `{receipt.baseline_id}`",
        f"- Git commit: `{receipt.git_commit}`",
        f"- Fixed cases: {receipt.total_case_count} (minimum {receipt.minimum_case_count})",
        f"- Input fingerprint: `{receipt.input_fingerprint}`",
        "- Release eligible: `false`",
        "",
        "## Reports",
        "",
        "| Evaluator | Cases | Dataset fingerprint | Report SHA-256 | Provider / model | Capture |",
        "|---|---:|---|---|---|---|",
    ]
    lines.extend(
        "| {kind} | {cases} | `{dataset}` | `{report}` | {provider} / {model} | {capture} |".format(
            kind=item.kind,
            cases=item.case_count,
            dataset=item.dataset_fingerprint,
            report=item.report_sha256,
            provider=item.provider,
            model=item.model,
            capture=item.capture_kind.value,
        )
        for item in receipt.reports
    )
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in receipt.limitations)
    lines.append("")
    return "\n".join(lines)


def _build_bidbench_control(root: Path, git_commit: str) -> BidBenchRunReport:
    report = evaluate_files(root / "dataset.json", root / "candidates" / "empty-control.json")
    return report.model_copy(
        update={
            "git_commit": git_commit,
            "provider": _NOT_APPLICABLE,
            "model": "empty-control",
            "provenance": _control_provenance("bidbench"),
        }
    )


def _build_retrieval_control(root: Path, git_commit: str) -> RetrievalEvaluationReport:
    dataset = load_retrieval_benchmark_dataset(root / "retrieval-development.json")
    run = RetrievalEvaluationRun(
        dataset_id=dataset.dataset_id,
        fixture_fingerprint=retrieval_fixture_fingerprint(dataset),
        retrieval_profile_id="bidpilot-control:lexical:0",
        strategy=RetrievalStrategy.SPARSE,
        candidate_limit=5,
        results=tuple(
            RetrievalQueryResult(
                query_id=case.id,
                hits=(
                    RetrievalBenchmarkHit(
                        chunk_id=case.relevant_chunk_ids[0],
                        project_id=case.authorized_project_id,
                        source_id=case.expected_locators[0].source_id,
                        locator=case.expected_locators[0],
                        locator_validation_status=CitationValidationStatus.VERIFIED,
                    ),
                ),
                degraded_reasons=case.required_degraded_reasons,
            )
            for case in dataset.queries
        ),
        git_commit=git_commit,
        provider=_NOT_APPLICABLE,
        model="retrieval-control",
        provenance=_control_provenance("retrieval"),
    )
    return score_retrieval_run(dataset, run)


def _build_memory_control(root: Path, git_commit: str) -> MemoryEvaluationReport:
    dataset = load_memory_benchmark_dataset(root / "memory-development.json")
    observations = []
    for case in dataset.cases:
        is_private = case.project_id is None
        scope = MemoryScope.USER_PRIVATE if is_private else MemoryScope.PROJECT_SHARED
        observations.append(
            MemoryContextObservation(
                case_id=case.id,
                org_id=case.org_id,
                user_id=case.user_id,
                project_id=case.project_id,
                memory_version=f"control-{case.id}",
                items=tuple(
                    MemoryContextItemObservation(
                        record_id=record_id,
                        scope=scope,
                        owner_user_id=case.user_id if is_private else None,
                        citation_count=1,
                        content_characters=1,
                    )
                    for record_id in case.expected_record_ids
                ),
                degraded_reasons=case.required_degraded_reasons,
            )
        )
    run = MemoryEvaluationRun(
        dataset_id=dataset.dataset_id,
        fixture_fingerprint=memory_fixture_fingerprint(dataset),
        policy_version="bidpilot-memory-control-v1",
        retrieval_profile_id="bidpilot-control:lexical:0",
        results=tuple(observations),
        git_commit=git_commit,
        provenance=_control_provenance("memory"),
    )
    return score_memory_run(dataset, run)


def _build_assistant_control(root: Path, git_commit: str) -> AssistantEvaluationReport:
    dataset = load_assistant_benchmark_dataset(root / "assistant-development.json")
    run = build_deterministic_assistant_run(
        dataset,
        router=_expected_fixture_router(dataset),
        router_version="expected-fixture-v2",
        git_commit=git_commit,
        provenance=_control_provenance("assistant"),
    ).model_copy(update={"provider": _NOT_APPLICABLE, "model": "expected-fixture"})
    return score_assistant_run(dataset, run)


def _expected_fixture_router(dataset):
    """Build a test-only router from declared expected outcomes.

    This keeps the offline control report reproducible without importing or
    exercising any production intent classifier.
    """

    cases = {(case.message, case.project_id): case for case in dataset.cases}

    def route(message: str, project_id: str | None) -> AssistantIntent:
        case = cases[(message, project_id)]
        arguments = {
            key: (
                project_id
                if key == "project_id" and project_id
                else "fixture-project"
                if key == "project_id"
                else "fixture-value"
            )
            for key in case.required_argument_keys
        }
        return AssistantIntent(
            mode=case.expected_mode,
            tool_name=case.expected_tool_name,
            arguments=arguments,
            missing_fields=list(case.expected_missing_fields),
        )

    return route


def _control_provenance(kind: str) -> EvaluationEvidenceProvenance:
    return EvaluationEvidenceProvenance(
        evidence_set_id="demo-smart-community-development",
        capture_id=f"development-baseline-{kind}-control",
        capture_kind=EvaluationCaptureKind.CONTROL_FIXTURE,
        review_level=EvaluationReviewLevel.UNREVIEWED,
        evaluator_version=_BASELINE_VERSION,
    )


def _bidbench_receipt(report: BidBenchRunReport) -> BaselineReportReceipt:
    return BaselineReportReceipt(
        kind="bidbench",
        dataset_id=report.dataset_id,
        dataset_role=report.dataset_role,
        dataset_fingerprint=report.dataset_sha256,
        report_sha256=_canonical_sha256(report.model_dump(mode="json")),
        case_count=report.metrics.counts.ground_truth_requirements,
        git_commit=report.git_commit or _NOT_APPLICABLE,
        provider=report.provider or _NOT_APPLICABLE,
        model=report.model or _NOT_APPLICABLE,
        capture_kind=report.provenance.capture_kind if report.provenance else EvaluationCaptureKind.CONTROL_FIXTURE,
        review_level=report.provenance.review_level if report.provenance else EvaluationReviewLevel.UNREVIEWED,
    )


def _retrieval_receipt(report: RetrievalEvaluationReport) -> BaselineReportReceipt:
    return BaselineReportReceipt(
        kind="retrieval",
        dataset_id=report.dataset_id,
        dataset_role=report.dataset_role,
        dataset_fingerprint=report.fixture_fingerprint,
        report_sha256=_canonical_sha256(report.model_dump(mode="json")),
        case_count=report.metrics.counts.query_count,
        git_commit=report.git_commit or _NOT_APPLICABLE,
        provider=report.provider or _NOT_APPLICABLE,
        model=report.model or _NOT_APPLICABLE,
        capture_kind=report.provenance.capture_kind if report.provenance else EvaluationCaptureKind.CONTROL_FIXTURE,
        review_level=report.provenance.review_level if report.provenance else EvaluationReviewLevel.UNREVIEWED,
    )


def _memory_receipt(report: MemoryEvaluationReport) -> BaselineReportReceipt:
    return BaselineReportReceipt(
        kind="memory",
        dataset_id=report.dataset_id,
        dataset_role=report.dataset_role,
        dataset_fingerprint=report.fixture_fingerprint,
        report_sha256=_canonical_sha256(report.model_dump(mode="json")),
        case_count=report.metrics.counts.case_count,
        git_commit=report.git_commit or _NOT_APPLICABLE,
        provider=_NOT_APPLICABLE,
        model=_NOT_APPLICABLE,
        capture_kind=report.provenance.capture_kind if report.provenance else EvaluationCaptureKind.CONTROL_FIXTURE,
        review_level=report.provenance.review_level if report.provenance else EvaluationReviewLevel.UNREVIEWED,
    )


def _assistant_receipt(report: AssistantEvaluationReport) -> BaselineReportReceipt:
    return BaselineReportReceipt(
        kind="assistant",
        dataset_id=report.dataset_id,
        dataset_role=report.dataset_role,
        dataset_fingerprint=report.fixture_fingerprint,
        report_sha256=_canonical_sha256(report.model_dump(mode="json")),
        case_count=report.metrics.counts.case_count,
        git_commit=report.git_commit or _NOT_APPLICABLE,
        provider=report.provider or _NOT_APPLICABLE,
        model=report.model or _NOT_APPLICABLE,
        capture_kind=report.provenance.capture_kind if report.provenance else EvaluationCaptureKind.CONTROL_FIXTURE,
        review_level=report.provenance.review_level if report.provenance else EvaluationReviewLevel.UNREVIEWED,
        controlled_capture_ready=report.capture_readiness.controlled_capture_ready,
    )


def _canonical_sha256(payload: object) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


__all__ = [
    "DEVELOPMENT_BASELINE_ID",
    "MIN_DEVELOPMENT_BASELINE_CASES",
    "BaselineReportReceipt",
    "DevelopmentBaselineReceipt",
    "DevelopmentBaselineResult",
    "build_development_baseline",
    "render_development_baseline_markdown",
    "write_development_baseline",
]
