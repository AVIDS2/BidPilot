from types import SimpleNamespace

import pytest

from app.adapters.provider_errors import ProviderInvocationError
from app.execution import model_usage as model_usage_module
from contracts.model_usage import ProviderUsageMeasurement
from contracts.usage_ledger import ModelUsageBudgetExceeded


class _FakeSession:
    def __init__(self, primary=None):
        self.primary = primary
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0
        self.closed = False

    def scalar(self, _statement):
        return self.primary

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def flush(self):
        self.flushes += 1

    def close(self):
        self.closed = True


def _patch_workflow_context(monkeypatch, session, reservations=None):
    run = SimpleNamespace(
        id="execution-1",
        project_id="project-1",
        input_json={"model_usage_reservation_key": "workflow:primary"},
    )
    runtime = SimpleNamespace(
        id="runtime-1",
        org_id="org-1",
        user_id="user-1",
        provider_config_id=None,
        input_json={"provider_source": "official"},
    )
    monkeypatch.setattr(model_usage_module, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        model_usage_module,
        "_workflow_context",
        lambda _db, _run_id: (run, runtime),
    )
    if reservations is not None:
        monkeypatch.setattr(
            model_usage_module,
            "_workflow_attempt_reservations",
            lambda _db, **_kwargs: reservations,
        )
    return run, runtime


def test_first_model_call_claims_the_api_preflight_hold(monkeypatch):
    primary = SimpleNamespace(
        provider_source="official",
        workload="workflow_execution",
        reserved_tokens=16_000,
        status="reserved",
    )
    session = _FakeSession(primary=primary)
    _patch_workflow_context(monkeypatch, session)

    call = model_usage_module.begin_workflow_model_call(
        run_id="execution-1",
        workload="workflow_requirement_extraction",
        operation_key="requirements-extraction",
    )

    assert call.reservation_key == "workflow:primary"
    assert call.workload == "workflow_requirement_extraction"
    assert primary.status == "dispatched"
    assert session.commits == 1
    assert session.closed is True


def test_later_model_call_preserves_unknown_dispatch_and_reserves_new_key(monkeypatch):
    primary = SimpleNamespace(
        provider_source="official",
        workload="workflow_execution",
        reserved_tokens=16_000,
        status="dispatched",
    )
    session = _FakeSession(primary=primary)
    _patch_workflow_context(monkeypatch, session)
    captured: list[dict] = []
    created = SimpleNamespace(status="reserved")
    monkeypatch.setattr(model_usage_module, "uuid4", lambda: "next-call")
    monkeypatch.setattr(
        model_usage_module,
        "reserve_model_tokens",
        lambda _db, **kwargs: captured.append(kwargs) or created,
    )

    call = model_usage_module.begin_workflow_model_call(
        run_id="execution-1",
        workload="workflow_draft",
        operation_key="draft-1-attempt-2",
    )

    assert primary.status == "uncertain"
    assert call.reservation_key == "workflow:primary:call:draft-1-attempt-2:next-call"
    assert created.status == "dispatched"
    assert captured == [
        {
            "org_id": "org-1",
            "user_id": "user-1",
            "provider_source": "official",
            "workload": "workflow_draft",
            "reservation_key": "workflow:primary:call:draft-1-attempt-2:next-call",
            "reserved_tokens": 16_000,
            "project_id": "project-1",
            "execution_run_id": "execution-1",
            "runtime_run_id": "runtime-1",
        }
    ]


def test_later_model_call_fails_before_provider_dispatch_when_budget_exhausted(monkeypatch):
    primary = SimpleNamespace(
        provider_source="official",
        workload="workflow_execution",
        reserved_tokens=16_000,
        status="settled",
    )
    session = _FakeSession(primary=primary)
    _patch_workflow_context(monkeypatch, session)
    monkeypatch.setattr(
        model_usage_module,
        "reserve_model_tokens",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ModelUsageBudgetExceeded("no capacity")),
    )

    with pytest.raises(ProviderInvocationError) as error:
        model_usage_module.begin_workflow_model_call(
            run_id="execution-1",
            workload="workflow_quality_review",
            operation_key="quality-review-1",
        )

    assert error.value.error_code == "organization_token_budget_exhausted"
    assert error.value.retryable is False
    assert session.rollbacks == 1


def test_hosted_official_workflow_rejects_missing_platform_ceiling(monkeypatch):
    primary = SimpleNamespace(
        provider_source="official",
        workload="workflow_execution",
        reserved_tokens=16_000,
        status="reserved",
    )
    session = _FakeSession(primary=primary)
    _patch_workflow_context(monkeypatch, session)
    monkeypatch.setenv("DOCPILOT_ENV", "production")
    monkeypatch.delenv("DOCPILOT_OFFICIAL_MONTHLY_TOKEN_CEILING", raising=False)

    with pytest.raises(ProviderInvocationError) as error:
        model_usage_module.begin_workflow_model_call(
            run_id="execution-1",
            workload="workflow_draft",
            operation_key="draft-1",
        )

    assert error.value.error_code == "official_token_budget_not_configured"
    assert error.value.retryable is False
    assert session.rollbacks == 1


def test_success_settles_only_its_own_dispatched_reservation(monkeypatch):
    session = _FakeSession()
    _patch_workflow_context(monkeypatch, session)
    settled: list[dict] = []
    monkeypatch.setattr(model_usage_module, "record_model_usage", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        model_usage_module,
        "settle_model_reservation",
        lambda _db, **kwargs: settled.append(kwargs),
    )

    model_usage_module.record_workflow_model_usage(
        run_id="execution-1",
        provider_type="openai",
        model_name="test-model",
        measurement=ProviderUsageMeasurement(input_tokens=10, output_tokens=5),
        workload="workflow_quality_review",
        reservation_key="workflow:primary:call:quality-review-1:call-1",
    )

    assert settled == [
        {
            "org_id": "org-1",
            "reservation_key": "workflow:primary:call:quality-review-1:call-1",
        }
    ]
    assert session.commits == 1


def test_known_non_billable_call_failure_releases_only_that_call(monkeypatch):
    session = _FakeSession()
    _patch_workflow_context(monkeypatch, session)
    reservation = SimpleNamespace(status="dispatched", settled_at=None)
    monkeypatch.setattr(model_usage_module, "_find_reservation", lambda *_args, **_kwargs: reservation)

    model_usage_module.resolve_workflow_model_call_failure(
        run_id="execution-1",
        reservation_key="workflow:primary",
        error_code="provider_auth_failed",
    )

    assert reservation.status == "released"
    assert reservation.settled_at is not None
    assert session.commits == 1


def test_terminal_unknown_failure_preserves_prior_uncertain_attempts(monkeypatch):
    session = _FakeSession()
    reservations = [
        SimpleNamespace(status="uncertain", settled_at=None),
        SimpleNamespace(status="dispatched", settled_at=None),
        SimpleNamespace(status="settled", settled_at=None),
    ]
    _patch_workflow_context(monkeypatch, session, reservations)

    model_usage_module.finalize_workflow_model_reservation_failure(
        run_id="execution-1",
        error_code="provider_timeout",
    )

    assert [reservation.status for reservation in reservations] == [
        "uncertain",
        "uncertain",
        "settled",
    ]
    assert session.flushes == 1
    assert session.commits == 1
