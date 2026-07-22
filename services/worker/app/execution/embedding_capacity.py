"""Worker-side capacity accounting for platform-owned embedding requests."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from uuid import uuid4

from sqlalchemy.orm import Session

from app.adapters.embedding import (
    EmbeddingResult,
    generate_embeddings_batch,
    get_embedding_profile,
)
from contracts import EmbeddingOutcome, EmbeddingOutcomeStatus
from contracts.embedding_metering import (
    EmbeddingMeteringContext,
    embedding_outcomes_are_definitely_unbilled,
    provider_reported_embedding_tokens,
    reserve_embedding_capacity,
    resolve_embedding_capacity_failure,
    settle_embedding_capacity,
)
from contracts.usage_budget_policy import (
    OfficialTokenCeilingConfigurationError,
    require_official_monthly_token_ceiling,
)
from contracts.usage_ledger import ModelUsageBudgetExceeded


logger = logging.getLogger(__name__)


class EmbeddingCapacityUnavailable(RuntimeError):
    """A safe no-dispatch outcome for an embedding request."""

    def __init__(self, error_code: str) -> None:
        super().__init__(error_code)
        self.error_code = error_code


def begin_official_embedding_call(
    db: Session,
    *,
    org_id: str,
    user_id: str | None,
    project_id: str | None,
    workload: str,
    texts: Sequence[str],
    provider_type: str,
    model_name: str,
    execution_run_id: str | None = None,
    runtime_run_id: str | None = None,
) -> EmbeddingMeteringContext:
    """Reserve capacity before the caller sends one embedding HTTP request."""
    try:
        token_limit_ceiling = require_official_monthly_token_ceiling()
    except OfficialTokenCeilingConfigurationError as exc:
        raise EmbeddingCapacityUnavailable("official_token_budget_not_configured") from exc

    context = EmbeddingMeteringContext(
        org_id=org_id,
        user_id=user_id,
        project_id=project_id,
        workload=workload,
        reservation_key=f"embedding:{workload}:{uuid4()}",
        provider_type=provider_type,
        model_name=model_name,
        execution_run_id=execution_run_id,
        runtime_run_id=runtime_run_id,
    )
    try:
        reserve_embedding_capacity(
            db,
            context=context,
            texts=texts,
            token_limit_ceiling=token_limit_ceiling,
        )
    except ModelUsageBudgetExceeded as exc:
        raise EmbeddingCapacityUnavailable("organization_token_budget_exhausted") from exc
    return context


def finalize_official_embedding_call(
    db: Session,
    *,
    context: EmbeddingMeteringContext,
    outcomes: Sequence[EmbeddingOutcome],
) -> None:
    """Settle one response by real usage or retain/release its reservation safely."""
    reported_tokens = provider_reported_embedding_tokens(outcomes)
    if reported_tokens is not None:
        settle_embedding_capacity(
            db,
            context=context,
            provider_reported_tokens=reported_tokens,
        )
        return
    resolve_embedding_capacity_failure(
        db,
        context=context,
        definitely_unbilled=embedding_outcomes_are_definitely_unbilled(outcomes),
    )


def _capacity_outcomes(
    *,
    profile_id: str | None,
    model_name: str,
    error_code: str,
    count: int,
) -> list[EmbeddingResult]:
    return [
        EmbeddingResult(
            status=EmbeddingOutcomeStatus.BUDGET_EXHAUSTED,
            model=model_name,
            profile_id=profile_id,
            error_code=error_code,
        )
        for _ in range(count)
    ]


def generate_metered_embeddings_batch(
    db: Session,
    *,
    org_id: str,
    user_id: str | None,
    project_id: str | None,
    workload: str,
    texts: Sequence[str],
    execution_run_id: str | None = None,
    runtime_run_id: str | None = None,
) -> list[EmbeddingResult]:
    """Send one metered embedding batch, retaining capacity for ambiguous outcomes."""
    if not texts:
        return []
    profile = get_embedding_profile()
    if profile is None:
        return generate_embeddings_batch(list(texts))

    try:
        context = begin_official_embedding_call(
            db,
            org_id=org_id,
            user_id=user_id,
            project_id=project_id,
            workload=workload,
            texts=texts,
            provider_type=profile.provider,
            model_name=profile.model,
            execution_run_id=execution_run_id,
            runtime_run_id=runtime_run_id,
        )
        # Do not expose source text to the provider until the hold is durable.
        db.commit()
    except EmbeddingCapacityUnavailable as exc:
        db.rollback()
        return _capacity_outcomes(
            profile_id=profile.identifier,
            model_name=profile.model,
            error_code=exc.error_code,
            count=len(texts),
        )
    except Exception:
        db.rollback()
        logger.exception("Embedding capacity preflight failed")
        return _capacity_outcomes(
            profile_id=profile.identifier,
            model_name=profile.model,
            error_code="embedding_metering_unavailable",
            count=len(texts),
        )

    outcomes = generate_embeddings_batch(list(texts))
    try:
        finalize_official_embedding_call(db, context=context, outcomes=outcomes)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Embedding usage settlement failed")
        return [
            EmbeddingResult(
                status=EmbeddingOutcomeStatus.TRANSIENT_FAILURE,
                model=profile.model,
                profile_id=profile.identifier,
                error_code="embedding_metering_unavailable",
            )
            for _ in texts
        ]
    return outcomes


def generate_metered_embedding(
    db: Session,
    *,
    org_id: str,
    user_id: str | None,
    project_id: str | None,
    workload: str,
    text: str,
    execution_run_id: str | None = None,
    runtime_run_id: str | None = None,
) -> EmbeddingResult:
    """Single-query convenience wrapper sharing the exact batch accounting path."""
    outcomes = generate_metered_embeddings_batch(
        db,
        org_id=org_id,
        user_id=user_id,
        project_id=project_id,
        workload=workload,
        texts=[text],
        execution_run_id=execution_run_id,
        runtime_run_id=runtime_run_id,
    )
    if outcomes:
        return outcomes[0]
    # ``texts`` is intentionally non-empty above; this is a defensive adapter
    # result, not a fabricated vector.
    return EmbeddingResult(
        status=EmbeddingOutcomeStatus.TRANSIENT_FAILURE,
        model="unknown",
        error_code="embedding_metering_unavailable",
    )
