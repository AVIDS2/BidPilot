from __future__ import annotations

from uuid import uuid4

import pytest

from app.auth.schemas import CurrentUser
from app.db import SessionLocal
from app.models import ModelUsageRecord, ModelUsageReservation, Organization, Project, User
from app.retrieval import metered_embedding
from contracts import EmbeddingOutcome, EmbeddingOutcomeStatus, RetrievalProfile


_PROFILE = RetrievalProfile(
    provider="openrouter",
    model="qwen/qwen3-embedding-8b",
    dimensions=1536,
    normalizer_version="bidpilot-lexical-v1",
)


def _seed_workspace() -> tuple[CurrentUser, str]:
    suffix = uuid4().hex[:10]
    db = SessionLocal()
    try:
        org = Organization(id=str(uuid4()), slug=f"metered-query-{suffix}", name="Metered Query")
        user = User(
            id=str(uuid4()),
            org_id=org.id,
            email=f"metered-query-{suffix}@example.test",
            display_name="Metered Query User",
            password_hash="test-only",
            role="member",
            email_verified=True,
        )
        project = Project(
            id=str(uuid4()),
            org_id=org.id,
            slug=f"metered-query-project-{suffix}",
            name="Metered Query Project",
            scenario_package="bidpilot",
        )
        db.add_all([org, user, project])
        db.commit()
        return (
            CurrentUser(
                id=user.id,
                email=user.email,
                display_name=user.display_name,
                role=user.role,
                org_id=org.id,
                org_slug=org.slug,
            ),
            project.id,
        )
    finally:
        db.close()


def _configure_official_embedding(monkeypatch: pytest.MonkeyPatch, *, ceiling: int) -> None:
    monkeypatch.setenv("DOCPILOT_ENV", "production")
    monkeypatch.setenv("DOCPILOT_OFFICIAL_MONTHLY_TOKEN_CEILING", str(ceiling))
    monkeypatch.setattr(metered_embedding, "get_embedding_profile", lambda: _PROFILE)


def test_metered_query_embedding_blocks_provider_dispatch_when_capacity_is_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_user, project_id = _seed_workspace()
    _configure_official_embedding(monkeypatch, ceiling=0)
    calls: list[str] = []
    monkeypatch.setattr(
        metered_embedding,
        "generate_query_embedding",
        lambda query, **_kwargs: calls.append(query),
    )

    outcome = metered_embedding.generate_metered_query_embedding(
        current_user=current_user,
        project_id=project_id,
        query="投标技术方案",
        workload="embedding_evidence_query",
    )

    assert outcome.status is EmbeddingOutcomeStatus.BUDGET_EXHAUSTED
    assert outcome.error_code == "organization_token_budget_exhausted"
    assert calls == []


def test_metered_query_embedding_settles_one_provider_usage_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_user, project_id = _seed_workspace()
    _configure_official_embedding(monkeypatch, ceiling=1000)
    calls: list[str] = []
    provider_outcome = EmbeddingOutcome(
        status=EmbeddingOutcomeStatus.SUCCESS,
        profile_id=_PROFILE.identifier,
        vector=[0.1] * 1536,
        token_count=7,
        usage_reported=True,
    )
    monkeypatch.setattr(
        metered_embedding,
        "generate_query_embedding",
        lambda query, **_kwargs: calls.append(query) or provider_outcome,
    )

    outcome = metered_embedding.generate_metered_query_embedding(
        current_user=current_user,
        project_id=project_id,
        query="投标技术方案",
        workload="embedding_evidence_query",
    )

    assert outcome is provider_outcome
    assert calls == ["投标技术方案"]
    db = SessionLocal()
    try:
        records = list(
            db.query(ModelUsageRecord)
            .filter(
                ModelUsageRecord.org_id == current_user.org_id,
                ModelUsageRecord.workload == "embedding_evidence_query",
            )
            .all()
        )
        assert len(records) == 1
        assert records[0].input_tokens == 7
        assert records[0].output_tokens == 0
        reservations = list(
            db.query(ModelUsageReservation)
            .filter(ModelUsageReservation.org_id == current_user.org_id)
            .all()
        )
        assert len(reservations) == 1
        assert reservations[0].status == "settled"
    finally:
        db.close()


def test_metered_query_embedding_keeps_an_uncertain_reservation_without_provider_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_user, project_id = _seed_workspace()
    _configure_official_embedding(monkeypatch, ceiling=1000)
    monkeypatch.setattr(
        metered_embedding,
        "generate_query_embedding",
        lambda *_args, **_kwargs: EmbeddingOutcome(
            status=EmbeddingOutcomeStatus.SUCCESS,
            profile_id=_PROFILE.identifier,
            vector=[0.1] * 1536,
            usage_reported=False,
        ),
    )

    outcome = metered_embedding.generate_metered_query_embedding(
        current_user=current_user,
        project_id=project_id,
        query="投标技术方案",
        workload="embedding_evidence_query",
    )

    assert outcome.is_success
    db = SessionLocal()
    try:
        assert db.query(ModelUsageRecord).filter(ModelUsageRecord.org_id == current_user.org_id).count() == 0
        reservation = (
            db.query(ModelUsageReservation)
            .filter(ModelUsageReservation.org_id == current_user.org_id)
            .one()
        )
        assert reservation.status == "uncertain"
    finally:
        db.close()
