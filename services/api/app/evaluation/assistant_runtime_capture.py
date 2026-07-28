"""Read-only AssistantBench capture from durable Operator runtime records.

The capture path intentionally exports only structured routing/policy facts.
It never serializes user messages, argument values, runtime identifiers, model
payloads, checkpoint state, or hidden reasoning into the benchmark artifact.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RuntimeAction, RuntimeApproval, RuntimeEvent, RuntimeRun
from app.runtime.registry import is_workflow_capability
from contracts import EvaluationEvidenceProvenance
from contracts.runtime import RuntimeEventType, RuntimePolicyOutcome

from .assistant_metrics import (
    AssistantBenchCase,
    AssistantBenchDataset,
    AssistantEvaluationRun,
    AssistantIntentObservation,
    fixture_fingerprint,
)


class _RuntimeCaptureModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class AssistantRuntimeCaptureItem(_RuntimeCaptureModel):
    """Private case-to-run mapping consumed only by the offline capture command."""

    case_id: str = Field(min_length=1, max_length=100)
    runtime_run_id: str = Field(min_length=1, max_length=100)
    runtime_project_id: str | None = Field(default=None, min_length=1, max_length=100)


class AssistantRuntimeCaptureManifest(_RuntimeCaptureModel):
    schema_version: Literal["1.0"] = "1.0"
    dataset_id: str = Field(min_length=1, max_length=100)
    fixture_fingerprint: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    router_version: str = Field(min_length=1, max_length=100)
    captures: tuple[AssistantRuntimeCaptureItem, ...] = Field(min_length=1)
    git_commit: str | None = Field(default=None, max_length=100)
    provider: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=255)
    latency_ms: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    provenance: EvaluationEvidenceProvenance | None = None

    @model_validator(mode="after")
    def validate_capture_ids(self) -> AssistantRuntimeCaptureManifest:
        case_ids = [item.case_id for item in self.captures]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("runtime capture manifest contains duplicate case ids")
        run_ids = [item.runtime_run_id for item in self.captures]
        if len(run_ids) != len(set(run_ids)):
            raise ValueError("runtime capture manifest cannot reuse one run for multiple cases")
        return self


def load_assistant_runtime_capture_manifest(path: Path) -> AssistantRuntimeCaptureManifest:
    try:
        return AssistantRuntimeCaptureManifest.model_validate_json(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid AssistantBench runtime capture manifest: {path}") from exc


def capture_assistant_runtime_run(
    db: Session,
    dataset: AssistantBenchDataset,
    manifest: AssistantRuntimeCaptureManifest,
) -> AssistantEvaluationRun:
    """Build one redacted benchmark run from approved Operator runtime traces."""
    expected_fingerprint = fixture_fingerprint(dataset)
    if manifest.dataset_id != dataset.dataset_id:
        raise ValueError("runtime capture manifest dataset_id does not match benchmark dataset")
    if manifest.fixture_fingerprint != expected_fingerprint:
        raise ValueError("runtime capture manifest fixture_fingerprint does not match benchmark dataset")

    cases = {case.id: case for case in dataset.cases}
    captures = {item.case_id: item for item in manifest.captures}
    if set(captures) != set(cases):
        raise ValueError("runtime capture manifest must map every benchmark case exactly once")

    observations = tuple(
        _capture_observation(
            db,
            case=case,
            capture=captures[case.id],
            expected_model=manifest.model,
        )
        for case in dataset.cases
    )
    return AssistantEvaluationRun(
        dataset_id=dataset.dataset_id,
        fixture_fingerprint=expected_fingerprint,
        router_version=manifest.router_version,
        results=observations,
        git_commit=manifest.git_commit,
        provider=manifest.provider,
        model=manifest.model,
        latency_ms=manifest.latency_ms,
        estimated_cost_usd=manifest.estimated_cost_usd,
        provenance=manifest.provenance,
    )


def _capture_observation(
    db: Session,
    *,
    case: AssistantBenchCase,
    capture: AssistantRuntimeCaptureItem,
    expected_model: str | None,
) -> AssistantIntentObservation:
    run = db.get(RuntimeRun, capture.runtime_run_id)
    if run is None:
        raise ValueError(f"runtime capture run is unavailable for case {case.id}")
    if run.kind != "assistant_turn" or run.engine != "langgraph_operator":
        raise ValueError(f"runtime capture case {case.id} must reference a LangGraph Operator assistant turn")
    if expected_model and run.model != expected_model:
        raise ValueError(f"runtime capture case {case.id} model does not match the capture manifest")

    plan = _load_single_plan(db, run, case_id=case.id)
    plan_mode = _plan_mode(plan, case_id=case.id)
    capability_name = _payload_text(plan.payload_json, "capability")
    missing_fields = _payload_string_list(plan.payload_json, "missing_fields")
    actions = list(
        db.scalars(
            select(RuntimeAction)
            .where(RuntimeAction.run_id == run.id)
            .order_by(RuntimeAction.created_at.asc(), RuntimeAction.id.asc())
        ).all()
    )
    if len(actions) > 1:
        raise ValueError(f"runtime capture case {case.id} has multiple actions; split it into one-turn cases")
    action = actions[0] if actions else None

    if plan_mode == "tool":
        if not capability_name:
            raise ValueError(f"runtime capture case {case.id} tool plan has no capability")
        if action is None:
            raise ValueError(f"runtime capture case {case.id} tool plan has no durable action")
        if action.capability_name != capability_name:
            raise ValueError(f"runtime capture case {case.id} plan/action capability mismatch")
        mode: Literal["workflow_trigger", "tool_action"] = (
            "workflow_trigger" if is_workflow_capability(capability_name) else "tool_action"
        )
        policy_outcome = _runtime_policy_outcome(action, case_id=case.id)
        approval = db.scalar(select(RuntimeApproval).where(RuntimeApproval.action_id == action.id))
        requires_typed_confirmation = bool(
            (approval.payload_json or {}).get("requires_typed_confirmation")
        ) if approval is not None else False
        argument_keys = tuple(sorted(key for key in (action.arguments_json or {}) if isinstance(key, str)))
        project_id = _redacted_project_scope(
            case=case,
            capture=capture,
            run=run,
            action=action,
        )
        return AssistantIntentObservation(
            case_id=case.id,
            mode=mode,
            tool_name=capability_name,
            argument_keys=argument_keys,
            project_id=project_id,
            policy_outcome=policy_outcome,
            requires_typed_confirmation=requires_typed_confirmation,
        )

    if action is not None:
        raise ValueError(f"runtime capture case {case.id} non-tool plan unexpectedly created an action")
    if plan_mode == "needs_input":
        if not capability_name or not missing_fields:
            raise ValueError(f"runtime capture case {case.id} missing-input plan is incomplete")
        return AssistantIntentObservation(
            case_id=case.id,
            mode="needs_input",
            tool_name=capability_name,
            missing_fields=missing_fields,
        )
    return AssistantIntentObservation(case_id=case.id, mode="answer")


def _load_single_plan(db: Session, run: RuntimeRun, *, case_id: str) -> RuntimeEvent:
    plans = list(
        db.scalars(
            select(RuntimeEvent)
            .where(
                RuntimeEvent.run_id == run.id,
                RuntimeEvent.event_type == RuntimeEventType.PLAN_PROPOSED.value,
            )
            .order_by(RuntimeEvent.sequence.asc())
        ).all()
    )
    if len(plans) != 1:
        raise ValueError(f"runtime capture case {case_id} must contain exactly one durable plan event")
    return plans[0]


def _plan_mode(event: RuntimeEvent, *, case_id: str) -> Literal["answer", "tool", "needs_input"]:
    mode = _payload_text(event.payload_json, "mode")
    if mode == "answer":
        return "answer"
    if mode == "tool":
        return "tool"
    if mode == "needs_input":
        return "needs_input"
    else:
        raise ValueError(f"runtime capture case {case_id} has an unsupported plan mode")


def _runtime_policy_outcome(action: RuntimeAction, *, case_id: str) -> RuntimePolicyOutcome:
    try:
        return RuntimePolicyOutcome(action.policy_outcome)
    except ValueError as exc:
        raise ValueError(f"runtime capture case {case_id} has an invalid policy outcome") from exc


def _redacted_project_scope(
    *,
    case: AssistantBenchCase,
    capture: AssistantRuntimeCaptureItem,
    run: RuntimeRun,
    action: RuntimeAction,
) -> str | None:
    if not case.expect_project_scope or case.project_id is None:
        return None
    if not capture.runtime_project_id:
        raise ValueError(f"runtime capture case {case.id} requires a private runtime_project_id mapping")
    action_project_id = (action.arguments_json or {}).get("project_id")
    observed_ids = {
        value
        for value in (run.project_id, action_project_id)
        if isinstance(value, str) and value
    }
    if capture.runtime_project_id not in observed_ids:
        raise ValueError(f"runtime capture case {case.id} does not retain the mapped project scope")
    if run.project_id and isinstance(action_project_id, str) and action_project_id != run.project_id:
        raise ValueError(f"runtime capture case {case.id} disagrees on project scope")
    return case.project_id


def _payload_text(payload: dict | None, key: str) -> str | None:
    value = (payload or {}).get(key)
    return value if isinstance(value, str) and value else None


def _payload_string_list(payload: dict | None, key: str) -> tuple[str, ...]:
    value = (payload or {}).get(key)
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


__all__ = [
    "AssistantRuntimeCaptureItem",
    "AssistantRuntimeCaptureManifest",
    "capture_assistant_runtime_run",
    "load_assistant_runtime_capture_manifest",
]
