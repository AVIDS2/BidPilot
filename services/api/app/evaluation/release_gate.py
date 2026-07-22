"""Policy-based release gates for BidPilot's offline evaluation artifacts.

The gate consumes already-redacted Benchmark reports. It never queries a model,
replays customer data, or treats a development fixture as production proof.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from contracts import EvaluationCaptureKind, EvaluationEvidenceProvenance, EvaluationReviewLevel

from .assistant_metrics import AssistantEvaluationReport
from .bidbench import BidBenchRunReport, BidBenchThresholds, check_thresholds
from .memory_metrics import MemoryEvaluationReport
from .retrieval_metrics import RetrievalEvaluationReport


class _QualityGateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class QualityGateMode(StrEnum):
    DEVELOPMENT = "development"
    RELEASE = "release"


class RetrievalGateThresholds(_QualityGateModel):
    min_recall_at_5: float | None = Field(default=None, ge=0, le=1)
    min_mean_reciprocal_rank: float | None = Field(default=None, ge=0, le=1)
    min_locator_validity_rate: float | None = Field(default=None, ge=0, le=1)
    min_mandatory_evidence_recall: float | None = Field(default=None, ge=0, le=1)
    min_cross_project_denial_rate: float | None = Field(default=None, ge=0, le=1)
    min_degraded_mode_pass_rate: float | None = Field(default=None, ge=0, le=1)


class MemoryGateThresholds(_QualityGateModel):
    min_expected_record_recall: float | None = Field(default=None, ge=0, le=1)
    min_isolation_pass_rate: float | None = Field(default=None, ge=0, le=1)
    min_provenance_validity_rate: float | None = Field(default=None, ge=0, le=1)
    min_private_ownership_pass_rate: float | None = Field(default=None, ge=0, le=1)
    min_context_budget_pass_rate: float | None = Field(default=None, ge=0, le=1)
    min_degraded_mode_pass_rate: float | None = Field(default=None, ge=0, le=1)


class AssistantGateThresholds(_QualityGateModel):
    """Release requirements for the governed Assistant router and policy boundary."""

    min_mode_accuracy: float | None = Field(default=None, ge=0, le=1)
    min_capability_route_accuracy: float | None = Field(default=None, ge=0, le=1)
    min_missing_input_accuracy: float | None = Field(default=None, ge=0, le=1)
    min_required_argument_accuracy: float | None = Field(default=None, ge=0, le=1)
    min_policy_outcome_accuracy: float | None = Field(default=None, ge=0, le=1)
    min_typed_confirmation_safety_rate: float | None = Field(default=None, ge=0, le=1)
    min_project_scope_safety_rate: float | None = Field(default=None, ge=0, le=1)
    max_unknown_capability_rate: float | None = Field(default=None, ge=0, le=1)


class QualityGatePolicy(_QualityGateModel):
    schema_version: Literal["1.1"] = "1.1"
    policy_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    bidbench_thresholds: BidBenchThresholds
    retrieval_thresholds: RetrievalGateThresholds
    memory_thresholds: MemoryGateThresholds
    assistant_thresholds: AssistantGateThresholds
    allowed_release_dataset_roles: tuple[str, ...] = ("regression", "hidden")
    allowed_release_capture_kinds: tuple[EvaluationCaptureKind, ...] = (
        EvaluationCaptureKind.CURRENT_PIPELINE,
        EvaluationCaptureKind.REVIEWED_SNAPSHOT,
    )
    max_report_age_hours: int = Field(default=168, ge=1, le=168)
    require_bidbench_model_metadata_for_release: bool = True
    require_assistant_model_metadata_for_release: bool = True
    require_git_commit_for_release: bool = True

    @field_validator("allowed_release_dataset_roles")
    @classmethod
    def normalize_release_dataset_roles(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(role.casefold() for role in value)
        if not normalized or any(not role for role in normalized):
            raise ValueError("allowed_release_dataset_roles must not be empty")
        if len(normalized) != len(set(normalized)):
            raise ValueError("allowed_release_dataset_roles must be unique")
        if "development" in normalized:
            raise ValueError("release policy must not allow development datasets")
        return normalized

    @field_validator("allowed_release_capture_kinds")
    @classmethod
    def validate_release_capture_kinds(
        cls,
        value: tuple[EvaluationCaptureKind, ...],
    ) -> tuple[EvaluationCaptureKind, ...]:
        if not value:
            raise ValueError("allowed_release_capture_kinds must not be empty")
        if len(value) != len(set(value)):
            raise ValueError("allowed_release_capture_kinds must be unique")
        if EvaluationCaptureKind.CONTROL_FIXTURE in value:
            raise ValueError("release policy must not allow control_fixture captures")
        return value

    @model_validator(mode="after")
    def require_real_thresholds(self) -> QualityGatePolicy:
        threshold_groups = {
            "bidbench_thresholds": self.bidbench_thresholds,
            "retrieval_thresholds": self.retrieval_thresholds,
            "memory_thresholds": self.memory_thresholds,
            "assistant_thresholds": self.assistant_thresholds,
        }
        for name, thresholds in threshold_groups.items():
            if not any(value is not None for value in thresholds.model_dump().values()):
                raise ValueError(f"{name} must contain at least one threshold")
        return self


class QualityGateInput(_QualityGateModel):
    kind: Literal["bidbench", "retrieval", "memory", "assistant"]
    dataset_id: str = Field(min_length=1, max_length=100)
    dataset_role: str = Field(min_length=1, max_length=30)
    fixture_fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    git_commit: str | None = Field(default=None, max_length=100)
    generated_at: datetime
    provenance: EvaluationEvidenceProvenance | None = None
    report_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")


class QualityGateReport(_QualityGateModel):
    schema_version: Literal["1.1"] = "1.1"
    generated_at: datetime
    mode: QualityGateMode
    policy_id: str
    policy_sha256: str
    expected_git_commit: str | None = None
    input_fingerprint: str
    inputs: tuple[QualityGateInput, ...]
    passed: bool
    release_eligible: bool
    failures: tuple[str, ...] = ()


def load_quality_gate_policy(path: Path) -> QualityGatePolicy:
    try:
        return QualityGatePolicy.model_validate_json(path.read_bytes())
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid quality-gate policy: {path}") from exc


def load_bidbench_report(path: Path) -> BidBenchRunReport:
    return _load_report(path, BidBenchRunReport, "BidBench")


def load_retrieval_report(path: Path) -> RetrievalEvaluationReport:
    return _load_report(path, RetrievalEvaluationReport, "retrieval")


def load_memory_report(path: Path) -> MemoryEvaluationReport:
    return _load_report(path, MemoryEvaluationReport, "memory")


def load_assistant_report(path: Path) -> AssistantEvaluationReport:
    return _load_report(path, AssistantEvaluationReport, "AssistantBench")


def evaluate_quality_gate(
    policy: QualityGatePolicy,
    *,
    bidbench_report: BidBenchRunReport,
    retrieval_report: RetrievalEvaluationReport,
    memory_report: MemoryEvaluationReport,
    assistant_report: AssistantEvaluationReport,
    mode: QualityGateMode,
    expected_git_commit: str | None = None,
) -> QualityGateReport:
    """Apply one reviewed policy to all required agent-quality reports."""
    inputs = (
        _bidbench_input(bidbench_report),
        _retrieval_input(retrieval_report),
        _memory_input(memory_report),
        _assistant_input(assistant_report),
    )
    failures: list[str] = []
    _check_metadata(
        failures,
        policy=policy,
        inputs=inputs,
        mode=mode,
        expected_git_commit=expected_git_commit,
    )
    if mode is QualityGateMode.RELEASE:
        _check_release_report_metadata(
            failures,
            policy=policy,
            bidbench_report=bidbench_report,
            assistant_report=assistant_report,
        )
    failures.extend(
        f"bidbench.{failure}"
        for failure in check_thresholds(bidbench_report, policy.bidbench_thresholds)
    )
    _check_retrieval_thresholds(failures, retrieval_report, policy.retrieval_thresholds)
    _check_memory_thresholds(failures, memory_report, policy.memory_thresholds)
    _check_assistant_thresholds(failures, assistant_report, policy.assistant_thresholds)

    policy_sha256 = _canonical_sha256(policy)
    input_fingerprint = _sha256_payload(
        {
            "policy_sha256": policy_sha256,
            "expected_git_commit": expected_git_commit,
            "inputs": [item.model_dump(mode="json") for item in inputs],
        }
    )
    passed = not failures
    return QualityGateReport(
        generated_at=datetime.now(UTC),
        mode=mode,
        policy_id=policy.policy_id,
        policy_sha256=policy_sha256,
        expected_git_commit=expected_git_commit,
        input_fingerprint=input_fingerprint,
        inputs=inputs,
        passed=passed,
        release_eligible=passed and mode is QualityGateMode.RELEASE,
        failures=tuple(failures),
    )


def render_quality_gate_markdown(report: QualityGateReport) -> str:
    lines = [
        "# BidPilot Quality Gate",
        "",
        f"- Policy: `{report.policy_id}`",
        f"- Mode: `{report.mode.value}`",
        f"- Passed: `{report.passed}`",
        f"- Release eligible: `{report.release_eligible}`",
        f"- Policy SHA-256: `{report.policy_sha256}`",
        f"- Input fingerprint: `{report.input_fingerprint}`",
        "",
        "## Inputs",
        "",
        "| Kind | Dataset | Role | Git commit | Report SHA-256 |",
        "|---|---|---|---|---|",
    ]
    lines.extend(
        f"| {item.kind} | {item.dataset_id} | {item.dataset_role} | {item.git_commit or 'missing'} | {item.report_sha256} |"
        for item in report.inputs
    )
    lines.extend(("", "## Evidence Provenance", ""))
    for item in report.inputs:
        provenance = item.provenance
        if provenance is None:
            lines.append(f"- {item.kind}: missing")
            continue
        lines.append(
            "- "
            f"{item.kind}: set `{provenance.evidence_set_id}`, capture `{provenance.capture_kind.value}`, "
            f"review `{provenance.review_level.value}`, attestation `{provenance.attestation_ref or 'missing'}`"
        )
    lines.extend(("", "## Failures", ""))
    if report.failures:
        lines.extend(f"- {failure}" for failure in report.failures)
    else:
        lines.append("- None")
    return "\n".join(lines)


def write_quality_gate_report(report: QualityGateReport, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "quality-gate.json"
    markdown_path = output_dir / "quality-gate.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(render_quality_gate_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def _check_metadata(
    failures: list[str],
    *,
    policy: QualityGatePolicy,
    inputs: tuple[QualityGateInput, ...],
    mode: QualityGateMode,
    expected_git_commit: str | None,
) -> None:
    if mode is QualityGateMode.RELEASE:
        for item in inputs:
            if item.dataset_role.casefold() not in policy.allowed_release_dataset_roles:
                failures.append(
                    f"{item.kind}.dataset_role={item.dataset_role} is not release-eligible"
                )
        if policy.require_git_commit_for_release and not expected_git_commit:
            failures.append("expected_git_commit is required for a release gate")
        _check_release_provenance(failures, policy=policy, inputs=inputs)

    if expected_git_commit:
        for item in inputs:
            if item.git_commit != expected_git_commit:
                failures.append(
                    f"{item.kind}.git_commit={item.git_commit or 'missing'} does not match "
                    f"expected {expected_git_commit}"
                )


def _check_release_report_metadata(
    failures: list[str],
    *,
    policy: QualityGatePolicy,
    bidbench_report: BidBenchRunReport,
    assistant_report: AssistantEvaluationReport,
) -> None:
    if policy.require_bidbench_model_metadata_for_release:
        _check_model_metadata(
            failures,
            kind="bidbench",
            values=(
                ("provider", bidbench_report.provider),
                ("model", bidbench_report.model),
                ("prompt_version", bidbench_report.prompt_version),
            ),
        )
    if policy.require_assistant_model_metadata_for_release:
        _check_model_metadata(
            failures,
            kind="assistant",
            values=(
                ("provider", assistant_report.provider),
                ("model", assistant_report.model),
                ("router_version", assistant_report.router_version),
            ),
        )


def _check_model_metadata(
    failures: list[str],
    *,
    kind: str,
    values: tuple[tuple[str, str | None], ...],
) -> None:
    missing = [field for field, value in values if not value]
    if missing:
        failures.append(f"{kind} missing release model metadata: {', '.join(missing)}")


def _check_release_provenance(
    failures: list[str],
    *,
    policy: QualityGatePolicy,
    inputs: tuple[QualityGateInput, ...],
) -> None:
    now = datetime.now(UTC)
    evidence_set_ids: set[str] = set()
    review_rank = {
        EvaluationReviewLevel.UNREVIEWED: 0,
        EvaluationReviewLevel.SINGLE_REVIEWER: 1,
        EvaluationReviewLevel.TWO_PERSON_REVIEW: 2,
    }
    required_review_rank = review_rank[EvaluationReviewLevel.TWO_PERSON_REVIEW]
    capture_ids: set[str] = set()

    for item in inputs:
        provenance = item.provenance
        if provenance is None:
            failures.append(f"{item.kind}.provenance is required for a release gate")
        else:
            evidence_set_ids.add(provenance.evidence_set_id)
            capture_ids.add(provenance.capture_id)
            if provenance.capture_kind not in policy.allowed_release_capture_kinds:
                failures.append(
                    f"{item.kind}.capture_kind={provenance.capture_kind.value} is not release-eligible"
                )
            if review_rank[provenance.review_level] < required_review_rank:
                failures.append(
                    f"{item.kind}.review_level={provenance.review_level.value} is below "
                    f"{EvaluationReviewLevel.TWO_PERSON_REVIEW.value}"
                )
            if not provenance.attestation_ref:
                failures.append(f"{item.kind}.attestation_ref is required for a release gate")

        if item.generated_at.tzinfo is None:
            failures.append(f"{item.kind}.generated_at must include a timezone")
            continue
        age = now - item.generated_at.astimezone(UTC)
        if age < timedelta(minutes=-5):
            failures.append(f"{item.kind}.generated_at is in the future")
        elif age > timedelta(hours=policy.max_report_age_hours):
            failures.append(
                f"{item.kind}.report_age_hours={age.total_seconds() / 3600:.2f} exceeds "
                f"{policy.max_report_age_hours}"
            )

    if len(evidence_set_ids) > 1:
        failures.append("release evidence reports must share one evidence_set_id")
    if len(capture_ids) > 1:
        failures.append("release evidence reports must share one capture_id")


def _check_retrieval_thresholds(
    failures: list[str],
    report: RetrievalEvaluationReport,
    thresholds: RetrievalGateThresholds,
) -> None:
    metrics = report.metrics
    _check_minimums(
        failures,
        "retrieval",
        (
            ("recall_at_5", metrics.recall_at_5, thresholds.min_recall_at_5),
            (
                "mean_reciprocal_rank",
                metrics.mean_reciprocal_rank,
                thresholds.min_mean_reciprocal_rank,
            ),
            (
                "locator_validity_rate",
                metrics.locator_validity_rate,
                thresholds.min_locator_validity_rate,
            ),
            (
                "mandatory_evidence_recall",
                metrics.mandatory_evidence_recall,
                thresholds.min_mandatory_evidence_recall,
            ),
            (
                "cross_project_denial_rate",
                metrics.cross_project_denial_rate,
                thresholds.min_cross_project_denial_rate,
            ),
            (
                "degraded_mode_pass_rate",
                metrics.degraded_mode_pass_rate,
                thresholds.min_degraded_mode_pass_rate,
            ),
        ),
    )


def _check_memory_thresholds(
    failures: list[str],
    report: MemoryEvaluationReport,
    thresholds: MemoryGateThresholds,
) -> None:
    metrics = report.metrics
    _check_minimums(
        failures,
        "memory",
        (
            (
                "expected_record_recall",
                metrics.expected_record_recall,
                thresholds.min_expected_record_recall,
            ),
            ("isolation_pass_rate", metrics.isolation_pass_rate, thresholds.min_isolation_pass_rate),
            (
                "provenance_validity_rate",
                metrics.provenance_validity_rate,
                thresholds.min_provenance_validity_rate,
            ),
            (
                "private_ownership_pass_rate",
                metrics.private_ownership_pass_rate,
                thresholds.min_private_ownership_pass_rate,
            ),
            (
                "context_budget_pass_rate",
                metrics.context_budget_pass_rate,
                thresholds.min_context_budget_pass_rate,
            ),
            (
                "degraded_mode_pass_rate",
                metrics.degraded_mode_pass_rate,
                thresholds.min_degraded_mode_pass_rate,
            ),
        ),
    )


def _check_assistant_thresholds(
    failures: list[str],
    report: AssistantEvaluationReport,
    thresholds: AssistantGateThresholds,
) -> None:
    metrics = report.metrics
    _check_minimums(
        failures,
        "assistant",
        (
            ("mode_accuracy", metrics.mode_accuracy, thresholds.min_mode_accuracy),
            (
                "capability_route_accuracy",
                metrics.capability_route_accuracy,
                thresholds.min_capability_route_accuracy,
            ),
            (
                "missing_input_accuracy",
                metrics.missing_input_accuracy,
                thresholds.min_missing_input_accuracy,
            ),
            (
                "required_argument_accuracy",
                metrics.required_argument_accuracy,
                thresholds.min_required_argument_accuracy,
            ),
            (
                "policy_outcome_accuracy",
                metrics.policy_outcome_accuracy,
                thresholds.min_policy_outcome_accuracy,
            ),
            (
                "typed_confirmation_safety_rate",
                metrics.typed_confirmation_safety_rate,
                thresholds.min_typed_confirmation_safety_rate,
            ),
            (
                "project_scope_safety_rate",
                metrics.project_scope_safety_rate,
                thresholds.min_project_scope_safety_rate,
            ),
        ),
    )
    if (
        thresholds.max_unknown_capability_rate is not None
        and metrics.unknown_capability_rate > thresholds.max_unknown_capability_rate
    ):
        failures.append(
            "assistant.unknown_capability_rate="
            f"{metrics.unknown_capability_rate:.4f} exceeds maximum "
            f"{thresholds.max_unknown_capability_rate:.4f}"
        )


def _check_minimums(
    failures: list[str],
    prefix: str,
    metrics: tuple[tuple[str, float | None, float | None], ...],
) -> None:
    for name, actual, minimum in metrics:
        if minimum is None:
            continue
        if actual is None:
            failures.append(f"{prefix}.{name} is unavailable but requires minimum {minimum:.4f}")
        elif actual < minimum:
            failures.append(f"{prefix}.{name}={actual:.4f} is below minimum {minimum:.4f}")


def _bidbench_input(report: BidBenchRunReport) -> QualityGateInput:
    return QualityGateInput(
        kind="bidbench",
        dataset_id=report.dataset_id,
        dataset_role=report.dataset_role,
        fixture_fingerprint=report.input_fingerprint,
        git_commit=report.git_commit,
        generated_at=report.generated_at,
        provenance=report.provenance,
        report_sha256=_canonical_sha256(report),
    )


def _retrieval_input(report: RetrievalEvaluationReport) -> QualityGateInput:
    return QualityGateInput(
        kind="retrieval",
        dataset_id=report.dataset_id,
        dataset_role=report.dataset_role,
        fixture_fingerprint=report.fixture_fingerprint,
        git_commit=report.git_commit,
        generated_at=report.generated_at,
        provenance=report.provenance,
        report_sha256=_canonical_sha256(report),
    )


def _memory_input(report: MemoryEvaluationReport) -> QualityGateInput:
    return QualityGateInput(
        kind="memory",
        dataset_id=report.dataset_id,
        dataset_role=report.dataset_role,
        fixture_fingerprint=report.fixture_fingerprint,
        git_commit=report.git_commit,
        generated_at=report.generated_at,
        provenance=report.provenance,
        report_sha256=_canonical_sha256(report),
    )


def _assistant_input(report: AssistantEvaluationReport) -> QualityGateInput:
    return QualityGateInput(
        kind="assistant",
        dataset_id=report.dataset_id,
        dataset_role=report.dataset_role,
        fixture_fingerprint=report.fixture_fingerprint,
        git_commit=report.git_commit,
        generated_at=report.generated_at,
        provenance=report.provenance,
        report_sha256=_canonical_sha256(report),
    )


def _load_report(path: Path, model: type[BaseModel], name: str) -> BaseModel:
    try:
        return model.model_validate_json(path.read_bytes())
    except (OSError, ValidationError) as exc:
        raise ValueError(f"invalid {name} report: {path}") from exc


def _canonical_sha256(model: BaseModel) -> str:
    return _sha256_payload(model.model_dump(mode="json"))


def _sha256_payload(payload: object) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


__all__ = [
    "AssistantGateThresholds",
    "MemoryGateThresholds",
    "QualityGateInput",
    "QualityGateMode",
    "QualityGatePolicy",
    "QualityGateReport",
    "RetrievalGateThresholds",
    "evaluate_quality_gate",
    "load_bidbench_report",
    "load_assistant_report",
    "load_memory_report",
    "load_quality_gate_policy",
    "load_retrieval_report",
    "render_quality_gate_markdown",
    "write_quality_gate_report",
]
