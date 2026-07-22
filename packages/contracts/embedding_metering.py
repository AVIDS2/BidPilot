"""Shared, redacted capacity accounting for server-owned embedding calls."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .model_usage import ProviderUsageMeasurement
from .models import ModelUsageReservation
from .retrieval import EmbeddingOutcome, EmbeddingOutcomeStatus
from .usage_ledger import (
    ACTIVE_RESERVATION_STATUSES,
    ProviderUsageSource,
    mark_model_reservation_uncertain,
    record_model_usage,
    release_model_reservation,
    reserve_model_tokens,
    settle_model_reservation,
)


@dataclass(frozen=True)
class EmbeddingMeteringContext:
    """Metadata safe to retain for one embedding HTTP request."""

    org_id: str
    user_id: str | None
    project_id: str | None
    workload: str
    reservation_key: str
    provider_type: str
    model_name: str
    provider_source: ProviderUsageSource = "official"
    execution_run_id: str | None = None
    runtime_run_id: str | None = None


def conservative_embedding_token_upper_bound(texts: Sequence[str]) -> int:
    """Reserve a safe upper bound without claiming a provider tokenizer match.

    UTF-8 byte length is deliberately conservative for modern text tokenizers;
    the small per-input allowance covers request framing and special tokens.
    """
    if not texts:
        raise ValueError("embedding request requires at least one input")
    return sum(len(text.encode("utf-8")) + 8 for text in texts)


def reserve_embedding_capacity(
    db: Session,
    *,
    context: EmbeddingMeteringContext,
    texts: Sequence[str],
    token_limit_ceiling: int | None,
) -> ModelUsageReservation | None:
    """Create and mark a pre-dispatch reservation for one embedding request."""
    reservation = reserve_model_tokens(
        db,
        org_id=context.org_id,
        user_id=context.user_id,
        provider_source=context.provider_source,
        workload=context.workload,
        reservation_key=context.reservation_key,
        reserved_tokens=conservative_embedding_token_upper_bound(texts),
        project_id=context.project_id,
        execution_run_id=context.execution_run_id,
        runtime_run_id=context.runtime_run_id,
        token_limit_ceiling=token_limit_ceiling,
    )
    if reservation is not None and reservation.status == "reserved":
        reservation.status = "dispatched"
        db.flush()
    return reservation


def settle_embedding_capacity(
    db: Session,
    *,
    context: EmbeddingMeteringContext,
    provider_reported_tokens: int | None,
) -> bool:
    """Record one provider response once, or retain capacity when usage is absent."""
    if provider_reported_tokens is not None and provider_reported_tokens < 0:
        raise ValueError("provider-reported embedding tokens must be non-negative")

    reservation = db.scalar(
        select(ModelUsageReservation)
        .where(
            ModelUsageReservation.org_id == context.org_id,
            ModelUsageReservation.reservation_key == context.reservation_key,
        )
        .with_for_update()
    )
    if reservation is not None and reservation.status not in ACTIVE_RESERVATION_STATUSES:
        return False
    if provider_reported_tokens is None:
        if reservation is not None:
            mark_model_reservation_uncertain(
                db,
                org_id=context.org_id,
                reservation_key=context.reservation_key,
            )
        return False

    record_model_usage(
        db,
        org_id=context.org_id,
        user_id=context.user_id,
        project_id=context.project_id,
        execution_run_id=context.execution_run_id,
        runtime_run_id=context.runtime_run_id,
        provider_source=context.provider_source,
        provider_type=context.provider_type,
        model_name=context.model_name,
        workload=context.workload,
        measurement=ProviderUsageMeasurement(input_tokens=provider_reported_tokens),
    )
    if reservation is not None:
        settle_model_reservation(
            db,
            org_id=context.org_id,
            reservation_key=context.reservation_key,
        )
    return True


def resolve_embedding_capacity_failure(
    db: Session,
    *,
    context: EmbeddingMeteringContext,
    definitely_unbilled: bool,
) -> None:
    """Release known-free failures; retain ambiguous provider outcomes."""
    if definitely_unbilled:
        release_model_reservation(
            db,
            org_id=context.org_id,
            reservation_key=context.reservation_key,
        )
        return
    mark_model_reservation_uncertain(
        db,
        org_id=context.org_id,
        reservation_key=context.reservation_key,
    )


def provider_reported_embedding_tokens(outcomes: Sequence[EmbeddingOutcome]) -> int | None:
    """Return one batch-level token count only when every outcome agrees."""
    if not outcomes or not all(outcome.usage_reported for outcome in outcomes):
        return None
    token_counts = {outcome.token_count for outcome in outcomes}
    return token_counts.pop() if len(token_counts) == 1 else None


def embedding_outcomes_are_definitely_unbilled(outcomes: Sequence[EmbeddingOutcome]) -> bool:
    """Identify failures known to occur before a provider can charge a request."""
    return bool(outcomes) and all(
        outcome.status
        in {
            EmbeddingOutcomeStatus.NOT_CONFIGURED,
            EmbeddingOutcomeStatus.PERMANENT_FAILURE,
        }
        for outcome in outcomes
    )
