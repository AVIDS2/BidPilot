"""Persist redacted model metering for Worker-owned workflow invocations."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import or_, select

from app.adapters.provider_errors import ProviderInvocationError
from app.db import SessionLocal
from app.models import ExecutionRun, ModelUsageReservation, RuntimeRun
from contracts.model_usage import ProviderUsageMeasurement
from contracts.usage_ledger import (
    ModelUsageBudgetExceeded,
    record_model_usage,
    reserve_model_tokens,
    settle_model_reservation,
)
from contracts.usage_budget_policy import (
    OfficialTokenCeilingConfigurationError,
    require_official_monthly_token_ceiling,
)


logger = logging.getLogger(__name__)

_DEFINITELY_UNBILLED_PROVIDER_ERRORS = {
    "organization_token_budget_exhausted",
    "provider_not_configured",
    "provider_config_missing",
    "provider_auth_failed",
    "provider_model_unavailable",
    "provider_request_invalid",
    "official_token_budget_not_configured",
    "model_usage_reservation_missing",
    "memory_graph_input_invalid",
    "memory_graph_policy_unsupported",
    "memory_graph_reused",
    "memory_graph_run_not_found",
    "memory_graph_source_changed_before_dispatch",
    "memory_graph_source_not_eligible",
}
_DISPATCHED_OR_RESERVED_STATUSES = {"reserved", "dispatched"}


@dataclass(frozen=True)
class WorkflowModelCall:
    """The durable budget hold associated with one physical provider request."""

    reservation_key: str | None
    workload: str


def _workflow_context(db, run_id: str) -> tuple[ExecutionRun, RuntimeRun] | None:
    run = db.get(ExecutionRun, run_id)
    if run is None:
        return None
    runtime_run_id = (run.input_json or {}).get("runtime_run_id")
    runtime = db.get(RuntimeRun, runtime_run_id) if isinstance(runtime_run_id, str) else None
    if runtime is None:
        runtime = db.scalar(
            select(RuntimeRun).where(RuntimeRun.execution_run_id == run_id).limit(1)
        )
    if runtime is None:
        return None
    return run, runtime


def _reservation_key(run: ExecutionRun) -> str | None:
    key = (run.input_json or {}).get("model_usage_reservation_key")
    return key if isinstance(key, str) and key else None


def _workflow_attempt_reservations(
    db,
    *,
    org_id: str,
    primary_key: str,
) -> list[ModelUsageReservation]:
    """Lock every budget hold created for one workflow execution."""
    return list(
        db.scalars(
            select(ModelUsageReservation)
            .where(
                ModelUsageReservation.org_id == org_id,
                or_(
                    ModelUsageReservation.reservation_key == primary_key,
                    ModelUsageReservation.reservation_key.like(f"{primary_key}:%"),
                ),
            )
            .with_for_update()
        )
    )


def _provider_source(runtime: RuntimeRun) -> str:
    configured_source = (runtime.input_json or {}).get("provider_source")
    if configured_source in {"official", "byok"}:
        return configured_source
    return "byok" if runtime.provider_config_id else "official"


def _token_limit_ceiling_for_source(provider_source: str) -> int | None:
    if provider_source != "official":
        return None
    try:
        return require_official_monthly_token_ceiling()
    except OfficialTokenCeilingConfigurationError as exc:
        raise ProviderInvocationError(
            "official_token_budget_not_configured",
            "平台模型额度保护尚未正确配置，已拒绝执行。",
            retryable=False,
        ) from exc


def _call_reservation_key(primary_key: str, operation_key: str) -> str:
    """Generate a bounded internal key for a subsequent physical dispatch."""
    normalized = re.sub(r"[^a-z0-9:_-]+", "-", operation_key.lower()).strip("-:")
    normalized = normalized[:80] or "workflow-model"
    return f"{primary_key}:call:{normalized}:{uuid4()}"


def _find_reservation(
    db,
    *,
    org_id: str,
    reservation_key: str,
) -> ModelUsageReservation | None:
    return db.scalar(
        select(ModelUsageReservation)
        .where(
            ModelUsageReservation.org_id == org_id,
            ModelUsageReservation.reservation_key == reservation_key,
        )
        .with_for_update()
    )


def begin_workflow_model_call(
    *,
    run_id: str,
    workload: str,
    operation_key: str,
) -> WorkflowModelCall:
    """Commit a capacity hold immediately before a physical provider request.

    API preflight creates the first ``reserved`` hold. The first model node to
    run claims it by switching it to ``dispatched``. Any later call receives a
    fresh key. If execution is replayed while a previous request is still
    ``dispatched``, that old request becomes ``uncertain`` before a new request
    is allowed to leave the process.
    """
    db = SessionLocal()
    try:
        context = _workflow_context(db, run_id)
        if context is None:
            logger.warning("Cannot begin model call without workflow runtime: run=%s", run_id)
            return WorkflowModelCall(reservation_key=None, workload=workload)
        run, runtime = context
        primary_key = _reservation_key(run)
        if not primary_key:
            return WorkflowModelCall(reservation_key=None, workload=workload)
        primary = _find_reservation(
            db,
            org_id=runtime.org_id,
            reservation_key=primary_key,
        )
        provider_source = _provider_source(runtime)
        token_limit_ceiling = _token_limit_ceiling_for_source(provider_source)
        # A local workspace can remain unmetered. Hosted official execution,
        # however, must always have committed preflight capacity before I/O.
        if primary is None:
            if token_limit_ceiling is not None:
                raise ProviderInvocationError(
                    "model_usage_reservation_missing",
                    "本次平台模型调用缺少已确认的额度预留，已拒绝执行。",
                    retryable=False,
                )
            return WorkflowModelCall(reservation_key=None, workload=workload)

        if primary.status == "reserved":
            primary.status = "dispatched"
            db.flush()
            db.commit()
            return WorkflowModelCall(reservation_key=primary_key, workload=workload)

        # A node restart after network I/O cannot prove the first request was
        # free. Preserve it before dispatching a new physical request.
        if primary.status == "dispatched":
            primary.status = "uncertain"

        reservation_key = _call_reservation_key(primary_key, operation_key)
        reservation_kwargs = {
            "org_id": runtime.org_id,
            "user_id": runtime.user_id,
            "provider_source": primary.provider_source,
            "workload": workload,
            "reservation_key": reservation_key,
            "reserved_tokens": primary.reserved_tokens,
            "project_id": run.project_id,
            "execution_run_id": run.id,
            "runtime_run_id": runtime.id,
        }
        if token_limit_ceiling is not None:
            reservation_kwargs["token_limit_ceiling"] = token_limit_ceiling
        reservation = reserve_model_tokens(
            db,
            **reservation_kwargs,  # type: ignore[arg-type]
        )
        if reservation is not None:
            reservation.status = "dispatched"
        # Never hold the budget lock while a provider handles the request.
        db.commit()
        return WorkflowModelCall(reservation_key=reservation_key, workload=workload)
    except ModelUsageBudgetExceeded as exc:
        db.rollback()
        raise ProviderInvocationError(
            "organization_token_budget_exhausted",
            "工作区本月 AI token 预算已用尽，请联系工作区管理员。",
            retryable=False,
        ) from exc
    except Exception:
        db.rollback()
        logger.exception("Failed to begin model call for workflow run %s", run_id)
        raise
    finally:
        db.close()


def mark_workflow_model_call_uncertain(*, run_id: str, reservation_key: str | None) -> None:
    """Keep one dispatched call reserved when its provider outcome is unknown."""
    if reservation_key is None:
        return
    db = SessionLocal()
    try:
        context = _workflow_context(db, run_id)
        if context is None:
            return
        _run, runtime = context
        reservation = _find_reservation(
            db,
            org_id=runtime.org_id,
            reservation_key=reservation_key,
        )
        if reservation is not None and reservation.status in _DISPATCHED_OR_RESERVED_STATUSES:
            reservation.status = "uncertain"
            db.flush()
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to mark model call uncertain for workflow run %s", run_id)
    finally:
        db.close()


def resolve_workflow_model_call_failure(
    *,
    run_id: str,
    reservation_key: str | None,
    error_code: str,
) -> None:
    """Resolve one known provider outcome without touching other workflow calls."""
    if reservation_key is None:
        return
    db = SessionLocal()
    try:
        context = _workflow_context(db, run_id)
        if context is None:
            return
        _run, runtime = context
        reservation = _find_reservation(
            db,
            org_id=runtime.org_id,
            reservation_key=reservation_key,
        )
        if reservation is None:
            return
        if error_code in _DEFINITELY_UNBILLED_PROVIDER_ERRORS:
            if reservation.status in _DISPATCHED_OR_RESERVED_STATUSES:
                reservation.status = "released"
                reservation.settled_at = datetime.now(UTC)
        elif reservation.status in _DISPATCHED_OR_RESERVED_STATUSES:
            reservation.status = "uncertain"
        db.flush()
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to resolve model call for workflow run %s", run_id)
    finally:
        db.close()


def record_workflow_model_usage(
    *,
    run_id: str,
    provider_type: str,
    model_name: str,
    measurement: ProviderUsageMeasurement | None,
    workload: str = "workflow_draft",
    reservation_key: str | None = None,
) -> None:
    """Append a successful provider measurement without risking draft output."""
    db = SessionLocal()
    try:
        context = _workflow_context(db, run_id)
        if context is None:
            logger.warning("Cannot record model usage without workflow runtime: run=%s", run_id)
            return
        run, runtime = context
        if reservation_key is None:
            # Legacy execution paths have exactly one model call and consume
            # the API preflight reservation directly.
            reservation_key = _reservation_key(run)
        if measurement is None:
            if reservation_key:
                reservation = _find_reservation(
                    db,
                    org_id=runtime.org_id,
                    reservation_key=reservation_key,
                )
                if reservation is not None and reservation.status in _DISPATCHED_OR_RESERVED_STATUSES:
                    reservation.status = "uncertain"
                    db.flush()
            db.commit()
            logger.warning("Provider omitted model usage counters: run=%s", run_id)
            return

        record_model_usage(
            db,
            org_id=runtime.org_id,
            user_id=runtime.user_id,
            project_id=run.project_id,
            execution_run_id=run.id,
            runtime_run_id=runtime.id,
            provider_source=_provider_source(runtime),  # type: ignore[arg-type]
            provider_type=provider_type,
            provider_config_id=runtime.provider_config_id,
            model_name=model_name or "provider-default",
            workload=workload,
            measurement=measurement,
        )
        if reservation_key:
            settle_model_reservation(
                db,
                org_id=runtime.org_id,
                reservation_key=reservation_key,
            )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to persist model usage for workflow run %s", run_id)
    finally:
        db.close()


def finalize_workflow_model_reservation_failure(*, run_id: str, error_code: str) -> None:
    """Resolve terminal workflow failure conservatively without provider details."""
    db = SessionLocal()
    try:
        context = _workflow_context(db, run_id)
        if context is None:
            return
        run, runtime = context
        primary_key = _reservation_key(run)
        if not primary_key:
            return
        reservations = _workflow_attempt_reservations(
            db,
            org_id=runtime.org_id,
            primary_key=primary_key,
        )
        now = datetime.now(UTC)
        for reservation in reservations:
            if reservation.status not in _DISPATCHED_OR_RESERVED_STATUSES:
                continue
            if error_code in _DEFINITELY_UNBILLED_PROVIDER_ERRORS:
                reservation.status = "released"
                reservation.settled_at = now
            else:
                reservation.status = "uncertain"
        db.flush()
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to resolve model reservation for workflow run %s", run_id)
    finally:
        db.close()
