from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.auth.schemas import CurrentUser
from app.assistant.router import _resolve_request_provider
from app.assistant.schemas import AssistantRequest
from app.drafting.schemas import DraftSectionRequest
from app.drafting.service import draft_section_command
from app.models import (
    ExecutionRun,
    ModelUsageReservation,
    Organization,
    OrganizationMembership,
    OrganizationUsageBudget,
    OrganizationUsageBudgetEvent,
    Project,
    TaskOutboxEvent,
    User,
)
from app.usage.service import (
    WORKFLOW_OPENAI_RESERVED_TOKENS,
    get_usage_quota,
    read_organization_usage_budget,
    update_organization_usage_budget,
)
from contracts.model_usage import (
    ProviderUsageMeasurement,
    normalize_anthropic_usage,
    normalize_openai_usage,
)
from contracts.usage_budget_policy import (
    OfficialTokenCeilingConfigurationError,
    require_official_monthly_token_ceiling,
)
from contracts.usage_ledger import (
    ModelUsageBudgetExceeded,
    mark_model_reservation_uncertain,
    model_usage_summary,
    record_model_usage,
    reserve_model_tokens,
    settle_model_reservation,
)


def _make_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _make_workspace(db: Session) -> tuple[Organization, User, Project]:
    org = Organization(slug="metered-workspace", name="Metered Workspace")
    db.add(org)
    db.flush()
    user = User(
        email="metered@example.com",
        display_name="Metered User",
        password_hash="test-only",
        role="member",
        email_verified=True,
        org_id=org.id,
    )
    db.add(user)
    db.flush()
    db.add(OrganizationMembership(org_id=org.id, user_id=user.id, role="owner"))
    project = Project(
        org_id=org.id,
        slug="metered-project",
        name="Metered Project",
        scenario_package="bidpilot",
    )
    db.add(project)
    db.commit()
    return org, user, project


def test_openai_and_anthropic_usage_normalizers_keep_only_numeric_counters() -> None:
    openai = normalize_openai_usage(
        {
            "usage": {
                "prompt_tokens": 11,
                "completion_tokens": 7,
                "total_tokens": 18,
                "prompt_tokens_details": {"cached_tokens": 3},
                "completion_tokens_details": {"reasoning_tokens": 2},
            },
            "choices": [{"message": {"content": "never stored"}}],
        }
    )
    anthropic = normalize_anthropic_usage(
        {
            "usage": {
                "input_tokens": 13,
                "output_tokens": 5,
                "cache_read_input_tokens": 4,
                "cache_creation_input_tokens": 6,
            },
            "content": [{"text": "never stored"}],
        }
    )

    assert openai is not None
    assert openai.input_tokens == 11
    assert openai.output_tokens == 7
    assert openai.reasoning_tokens == 2
    assert openai.cache_read_tokens == 3
    assert openai.total_tokens == 18
    assert anthropic is not None
    assert anthropic.input_tokens == 13
    assert anthropic.output_tokens == 5
    assert anthropic.cache_read_tokens == 4
    assert anthropic.cache_write_tokens == 6
    assert anthropic.total_tokens == 28


def test_token_budget_counts_active_reservations_then_settles_actual_usage() -> None:
    db = _make_db()
    try:
        org, user, project = _make_workspace(db)
        db.add(OrganizationUsageBudget(org_id=org.id, official_monthly_token_limit=100))
        db.commit()

        reservation = reserve_model_tokens(
            db,
            org_id=org.id,
            user_id=user.id,
            provider_source="official",
            workload="workflow_draft",
            reservation_key="workflow-one",
            reserved_tokens=60,
            project_id=project.id,
        )
        assert reservation is not None
        db.commit()

        with pytest.raises(ModelUsageBudgetExceeded):
            reserve_model_tokens(
                db,
                org_id=org.id,
                user_id=user.id,
                provider_source="official",
                workload="workflow_draft",
                reservation_key="workflow-two",
                reserved_tokens=50,
                project_id=project.id,
            )
        db.rollback()

        record_model_usage(
            db,
            org_id=org.id,
            user_id=user.id,
            project_id=project.id,
            provider_source="official",
            provider_type="openai",
            model_name="test-model",
            workload="workflow_draft",
            measurement=ProviderUsageMeasurement(input_tokens=25, output_tokens=15),
        )
        settle_model_reservation(db, org_id=org.id, reservation_key="workflow-one")
        db.commit()

        summary = model_usage_summary(db, org_id=org.id, provider_source="official")
        assert summary.total_tokens == 40
        assert summary.reserved_tokens == 0
        assert summary.token_limit == 100
        assert summary.remaining_tokens == 60

        next_reservation = reserve_model_tokens(
            db,
            org_id=org.id,
            user_id=user.id,
            provider_source="official",
            workload="workflow_draft",
            reservation_key="workflow-two",
            reserved_tokens=60,
            project_id=project.id,
        )
        assert next_reservation is not None
    finally:
        db.close()


def test_platform_ceiling_protects_an_organization_without_an_optional_budget() -> None:
    db = _make_db()
    try:
        org, user, project = _make_workspace(db)

        reservation = reserve_model_tokens(
            db,
            org_id=org.id,
            user_id=user.id,
            provider_source="official",
            workload="workflow_draft",
            reservation_key="platform-ceiling-first",
            reserved_tokens=80,
            project_id=project.id,
            token_limit_ceiling=100,
        )
        assert reservation is not None
        db.commit()

        with pytest.raises(ModelUsageBudgetExceeded):
            reserve_model_tokens(
                db,
                org_id=org.id,
                user_id=user.id,
                provider_source="official",
                workload="workflow_draft",
                reservation_key="platform-ceiling-blocked",
                reserved_tokens=21,
                project_id=project.id,
                token_limit_ceiling=100,
            )

        summary = model_usage_summary(
            db,
            org_id=org.id,
            provider_source="official",
            token_limit_ceiling=100,
        )
        assert summary.token_limit == 100
        assert summary.reserved_tokens == 80
        assert summary.remaining_tokens == 20
    finally:
        db.close()


def test_hosted_environment_requires_an_explicit_official_token_ceiling() -> None:
    with pytest.raises(OfficialTokenCeilingConfigurationError):
        require_official_monthly_token_ceiling({"DOCPILOT_ENV": "production"})

    assert require_official_monthly_token_ceiling(
        {
            "DOCPILOT_ENV": "production",
            "DOCPILOT_OFFICIAL_MONTHLY_TOKEN_CEILING": "0",
        }
    ) == 0


def test_unknown_provider_usage_stays_reserved_and_quota_summary_is_organization_scoped() -> None:
    db = _make_db()
    try:
        org, user, project = _make_workspace(db)
        db.add(OrganizationUsageBudget(org_id=org.id, official_monthly_token_limit=75))
        db.commit()
        reservation = reserve_model_tokens(
            db,
            org_id=org.id,
            user_id=user.id,
            provider_source="official",
            workload="assistant_planning",
            reservation_key="assistant-one",
            reserved_tokens=50,
            project_id=project.id,
        )
        assert reservation is not None
        mark_model_reservation_uncertain(db, org_id=org.id, reservation_key="assistant-one")
        db.commit()

        summary = model_usage_summary(db, org_id=org.id, provider_source="official")
        assert summary.total_tokens == 0
        assert summary.reserved_tokens == 50
        assert summary.remaining_tokens == 25

        quota = get_usage_quota(db, user.id)
        assert quota.official_model_usage.reserved_tokens == 50
        assert quota.byok_model_usage.total_tokens == 0
        assert quota.official_model_usage.cost_available is False
    finally:
        db.close()


def test_dispatched_reservation_counts_against_budget_until_settlement() -> None:
    db = _make_db()
    try:
        org, user, project = _make_workspace(db)
        db.add(OrganizationUsageBudget(org_id=org.id, official_monthly_token_limit=75))
        db.commit()
        reservation = reserve_model_tokens(
            db,
            org_id=org.id,
            user_id=user.id,
            provider_source="official",
            workload="workflow_execution",
            reservation_key="workflow-dispatched",
            reserved_tokens=50,
            project_id=project.id,
        )
        assert reservation is not None
        reservation.status = "dispatched"
        db.commit()

        active = model_usage_summary(db, org_id=org.id, provider_source="official")
        assert active.reserved_tokens == 50
        assert active.remaining_tokens == 25

        settle_model_reservation(db, org_id=org.id, reservation_key="workflow-dispatched")
        db.commit()

        settled = model_usage_summary(db, org_id=org.id, provider_source="official")
        assert settled.reserved_tokens == 0
        assert settled.remaining_tokens == 75
    finally:
        db.close()


def test_only_workspace_billing_owner_can_manage_optional_token_caps() -> None:
    db = _make_db()
    try:
        org, owner, _project = _make_workspace(db)
        read = update_organization_usage_budget(
            db,
            org_id=org.id,
            actor_user_id=owner.id,
            updates={"official_monthly_token_limit": 4_000},
        )
        assert read.can_manage is True
        assert read.official_monthly_token_limit == 4_000
        assert read.byok_monthly_token_limit is None

        member = User(
            email="member@example.com",
            display_name="Member",
            password_hash="test-only",
            role="member",
            email_verified=True,
            org_id=org.id,
        )
        db.add(member)
        db.flush()
        db.add(OrganizationMembership(org_id=org.id, user_id=member.id, role="member"))
        db.commit()

        with pytest.raises(PermissionError):
            update_organization_usage_budget(
                db,
                org_id=org.id,
                actor_user_id=member.id,
                updates={"byok_monthly_token_limit": 500},
            )

        persisted = read_organization_usage_budget(
            db,
            org_id=org.id,
            actor_user_id=owner.id,
        )
        assert persisted.official_monthly_token_limit == 4_000

        event = db.query(OrganizationUsageBudgetEvent).one()
        assert event.actor_user_id == owner.id
        assert event.event_type == "usage_budget.updated"
        assert event.previous_limits_json == {
            "official_monthly_token_limit": None,
            "byok_monthly_token_limit": None,
        }
        assert event.updated_limits_json == {
            "official_monthly_token_limit": 4_000,
            "byok_monthly_token_limit": None,
        }
    finally:
        db.close()


def test_workspace_budget_cannot_exceed_hosted_platform_ceiling(monkeypatch) -> None:
    db = _make_db()
    try:
        org, owner, _project = _make_workspace(db)
        monkeypatch.setenv("DOCPILOT_ENV", "production")
        monkeypatch.setenv("DOCPILOT_OFFICIAL_MONTHLY_TOKEN_CEILING", "1000")

        with pytest.raises(ValueError, match="cannot exceed the platform safety ceiling"):
            update_organization_usage_budget(
                db,
                org_id=org.id,
                actor_user_id=owner.id,
                updates={"official_monthly_token_limit": 1001},
            )

        read = update_organization_usage_budget(
            db,
            org_id=org.id,
            actor_user_id=owner.id,
            updates={"official_monthly_token_limit": 750},
        )
        assert read.official_platform_monthly_token_ceiling == 1000
        assert read.effective_official_monthly_token_limit == 750
    finally:
        db.close()


def test_budget_noop_does_not_create_policy_or_audit_row() -> None:
    db = _make_db()
    try:
        org, owner, _project = _make_workspace(db)

        read = update_organization_usage_budget(
            db,
            org_id=org.id,
            actor_user_id=owner.id,
            updates={},
        )

        assert read.official_monthly_token_limit is None
        assert db.query(OrganizationUsageBudget).count() == 0
        assert db.query(OrganizationUsageBudgetEvent).count() == 0
    finally:
        db.close()


def test_workflow_command_reserves_capacity_before_dispatch(monkeypatch) -> None:
    db = _make_db()
    try:
        org, user, project = _make_workspace(db)
        db.add(OrganizationUsageBudget(org_id=org.id, official_monthly_token_limit=18_000))
        db.commit()
        dispatched = []
        monkeypatch.setattr(
            "app.drafting.service.request_task_outbox_dispatch",
            lambda event_id: dispatched.append(event_id) or True,
        )
        current_user = CurrentUser(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role="admin",
            org_id=org.id,
        )

        response = draft_section_command(
            db,
            DraftSectionRequest(project_id=project.id, section_key="technical-approach"),
            current_user,
        )

        reservation = db.query(ModelUsageReservation).one()
        run = db.get(ExecutionRun, response.run_id)
        assert reservation.execution_run_id == response.run_id
        assert reservation.runtime_run_id == response.runtime_run_id
        assert reservation.reserved_tokens == WORKFLOW_OPENAI_RESERVED_TOKENS
        assert reservation.workload == "workflow_execution"
        assert run is not None
        assert run.input_json["model_usage_reservation_key"] == reservation.reservation_key
        outbox_event = db.query(TaskOutboxEvent).filter_by(execution_run_id=response.run_id).one()
        assert outbox_event.task_name == "worker.draft_section"
        assert dispatched == [outbox_event.id]
    finally:
        db.close()


def test_deleted_assistant_byok_config_never_falls_back_to_platform_key() -> None:
    db = _make_db()
    try:
        org, user, _project = _make_workspace(db)
        current_user = CurrentUser(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role="admin",
            org_id=org.id,
        )
        with pytest.raises(HTTPException) as error:
            _resolve_request_provider(
                db,
                current_user,
                AssistantRequest(message="查询项目", provider_config_id="deleted-provider-config"),
            )
        assert error.value.status_code == 404
        assert error.value.detail == "Provider config not found"
    finally:
        db.close()
