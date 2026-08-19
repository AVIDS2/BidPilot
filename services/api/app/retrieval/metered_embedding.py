"""Server-side query embeddings with durable official-provider cost controls."""

from __future__ import annotations

import logging
from uuid import uuid4

from app.auth.schemas import CurrentUser
from app.db import SessionLocal
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
    internal_unlimited_usage_enabled,
    require_official_monthly_token_ceiling,
)
from contracts.usage_ledger import ModelUsageBudgetExceeded

from .embedding import generate_query_embedding, get_embedding_profile


logger = logging.getLogger(__name__)


def _capacity_outcome(profile_id: str | None, error_code: str) -> EmbeddingOutcome:
    return EmbeddingOutcome(
        status=EmbeddingOutcomeStatus.BUDGET_EXHAUSTED,
        profile_id=profile_id,
        error_code=error_code,
    )


def generate_metered_query_embedding(
    *,
    current_user: CurrentUser,
    project_id: str | None,
    query: str,
    workload: str,
    timeout_seconds: float | None = None,
) -> EmbeddingOutcome:
    """Embed a query or safely fall back to lexical retrieval without bypassing cost policy."""
    profile = get_embedding_profile()
    if profile is None:
        return (
            generate_query_embedding(query)
            if timeout_seconds is None
            else generate_query_embedding(query, timeout_seconds=timeout_seconds)
        )
    if internal_unlimited_usage_enabled():
        return (
            generate_query_embedding(query)
            if timeout_seconds is None
            else generate_query_embedding(query, timeout_seconds=timeout_seconds)
        )

    try:
        token_limit_ceiling = require_official_monthly_token_ceiling()
    except OfficialTokenCeilingConfigurationError:
        return _capacity_outcome(profile.identifier, "official_token_budget_not_configured")

    context = EmbeddingMeteringContext(
        org_id=current_user.org_id,
        user_id=current_user.id,
        project_id=project_id,
        workload=workload,
        reservation_key=f"embedding:query:{uuid4()}",
        provider_type=profile.provider,
        model_name=profile.model,
    )
    db = SessionLocal()
    try:
        try:
            reserve_embedding_capacity(
                db,
                context=context,
                texts=[query],
                token_limit_ceiling=token_limit_ceiling,
            )
            # Commit before external I/O so the concurrent capacity hold is durable.
            db.commit()
        except ModelUsageBudgetExceeded:
            db.rollback()
            return _capacity_outcome(profile.identifier, "organization_token_budget_exhausted")
        except Exception:
            db.rollback()
            logger.exception("Embedding capacity preflight failed")
            return _capacity_outcome(profile.identifier, "embedding_metering_unavailable")

        outcome = (
            generate_query_embedding(query)
            if timeout_seconds is None
            else generate_query_embedding(query, timeout_seconds=timeout_seconds)
        )
        try:
            reported_tokens = provider_reported_embedding_tokens([outcome])
            if reported_tokens is not None:
                settle_embedding_capacity(
                    db,
                    context=context,
                    provider_reported_tokens=reported_tokens,
                )
            else:
                resolve_embedding_capacity_failure(
                    db,
                    context=context,
                    definitely_unbilled=embedding_outcomes_are_definitely_unbilled([outcome]),
                )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Embedding usage settlement failed")
        return outcome
    finally:
        db.close()


__all__ = ["generate_metered_query_embedding"]
