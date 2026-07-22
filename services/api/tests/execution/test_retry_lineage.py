from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.auth.schemas import CurrentUser
from app.drafting.schemas import DraftSectionRequest
from app.drafting.service import draft_section_command
from app.execution.service import retry_failed_run_command
from app.models import AuditEvent, ExecutionRun, Project, ProviderConfig, RuntimeRun, TaskOutboxEvent, UsageEvent, User
from app.runtime.service import create_workflow_bridge_run
from app.usage.schemas import ProviderSource


def _user(default_org_id: str, default_user_id: str) -> CurrentUser:
    return CurrentUser(
        id=default_user_id,
        email="dev@docpilot.local",
        display_name="Dev User",
        role="admin",
        org_id=default_org_id,
    )


def _project(test_db, default_org_id: str) -> Project:
    project = Project(
        org_id=default_org_id,
        name="Retry Lineage Project",
        slug=f"retry-lineage-{uuid.uuid4().hex[:8]}",
        scenario_package="bidpilot",
    )
    test_db.add(project)
    test_db.commit()
    return project


def _other_user(test_db, default_org_id: str) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        id=str(uuid.uuid4()),
        org_id=default_org_id,
        email=f"retry-owner-{suffix}@example.com",
        display_name="Retry Owner",
        role="admin",
        password_hash="test-password-hash",
    )
    test_db.add(user)
    test_db.flush()
    return user


def test_retry_creates_a_new_attempt_with_runtime_usage_and_audit_lineage(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    user = _user(default_org_id, default_user_id)
    project = _project(test_db, default_org_id)
    original = ExecutionRun(
        project_id=project.id,
        run_type="redraft_section",
        status="failed",
        input_json={"section_key": "technical-approach", "review_feedback": "Add delivery plan"},
    )
    test_db.add(original)
    test_db.commit()
    original_bridge = create_workflow_bridge_run(
        test_db,
        user,
        execution_run_id=original.id,
        project_id=project.id,
        reasoning_effort="high",
    )
    original_bridge.status = "failed"
    test_db.commit()

    quota_checks: list[tuple[str, str, ProviderSource]] = []
    dispatched: list[str] = []
    monkeypatch.setattr(
        "app.execution.service.check_workflow_quota",
        lambda _db, user_id, org_id, provider_source: quota_checks.append((user_id, org_id, provider_source)),
    )
    monkeypatch.setattr("app.execution.service.request_task_outbox_dispatch", lambda event_id: dispatched.append(event_id) or True)

    retried = retry_failed_run_command(test_db, original.id, user)

    test_db.refresh(original)
    retry = test_db.get(ExecutionRun, retried.id)
    assert retry is not None
    assert original.status == "failed"
    assert retry.id != original.id
    assert retry.parent_execution_run_id == original.id
    assert retry.attempt_number == 2
    assert retry.status == "queued"
    assert retry.input_json is not None
    assert retry.input_json["section_key"] == "technical-approach"
    assert retry.input_json["review_feedback"] == "Add delivery plan"
    assert retry.input_json["retry_of_execution_run_id"] == original.id

    retry_bridge = test_db.query(RuntimeRun).filter_by(execution_run_id=retry.id).one()
    assert retry.input_json["runtime_run_id"] == retry_bridge.id
    assert retry_bridge.parent_run_id == original_bridge.id
    assert retry_bridge.reasoning_effort == "high"
    assert retried.runtime_run_id == retry_bridge.id
    assert quota_checks == [(user.id, user.org_id, ProviderSource.OFFICIAL)]
    outbox_event = test_db.query(TaskOutboxEvent).filter_by(execution_run_id=retry.id).one()
    assert dispatched == [outbox_event.id]
    assert outbox_event.task_name == "worker.draft_section"
    assert outbox_event.args_json == [retry.id, project.id, "technical-approach"]
    assert outbox_event.kwargs_json == {
        "review_feedback": "Add delivery plan",
        "reasoning_effort": "high",
        "runtime_run_id": retry_bridge.id,
    }

    usage = test_db.query(UsageEvent).filter_by(execution_run_id=retry.id).one()
    assert usage.provider_source == ProviderSource.OFFICIAL.value
    assert usage.metadata_json == {"retry_of_execution_run_id": original.id, "attempt_number": 2}
    audit = test_db.query(AuditEvent).filter_by(project_id=project.id, event_type="run.retried").one()
    assert audit.payload_json == {
        "source_run_id": original.id,
        "retry_run_id": retry.id,
        "run_type": "redraft_section",
        "attempt_number": 2,
    }


@pytest.mark.parametrize("status", ["failed", "cancelled"])
def test_retry_allows_terminal_draft_attempts_without_mutating_the_source(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
    status: str,
) -> None:
    user = _user(default_org_id, default_user_id)
    project = _project(test_db, default_org_id)
    original = ExecutionRun(
        project_id=project.id,
        run_type="draft_section",
        status=status,
        input_json={"section_key": "technical-approach"},
    )
    test_db.add(original)
    test_db.commit()
    source_bridge = create_workflow_bridge_run(
        test_db,
        user,
        execution_run_id=original.id,
        project_id=project.id,
    )
    source_bridge.status = status
    test_db.commit()
    monkeypatch.setattr("app.execution.service.check_workflow_quota", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.execution.service.request_task_outbox_dispatch", lambda *_args, **_kwargs: None)

    retried = retry_failed_run_command(test_db, original.id, user)

    test_db.refresh(original)
    assert original.status == status
    assert retried.parent_execution_run_id == original.id
    assert retried.attempt_number == 2


def test_retry_rejects_legacy_workflows_without_a_runtime_bridge(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    user = _user(default_org_id, default_user_id)
    project = _project(test_db, default_org_id)
    original = ExecutionRun(
        project_id=project.id,
        run_type="draft_section",
        status="failed",
        input_json={"section_key": "technical-approach"},
    )
    test_db.add(original)
    test_db.commit()

    with pytest.raises(HTTPException, match="Legacy workflow") as error:
        retry_failed_run_command(test_db, original.id, user)
    assert error.value.status_code == 409


def test_retry_rejects_when_the_runtime_bridge_is_not_terminal(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    user = _user(default_org_id, default_user_id)
    project = _project(test_db, default_org_id)
    original = ExecutionRun(
        project_id=project.id,
        run_type="draft_section",
        status="failed",
        input_json={"section_key": "technical-approach"},
    )
    test_db.add(original)
    test_db.commit()
    create_workflow_bridge_run(
        test_db,
        user,
        execution_run_id=original.id,
        project_id=project.id,
    )

    with pytest.raises(HTTPException, match="Workflow runtime is not in a retryable terminal state") as error:
        retry_failed_run_command(test_db, original.id, user)
    assert error.value.status_code == 409


def test_retry_reuses_an_existing_active_child_attempt(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    user = _user(default_org_id, default_user_id)
    project = _project(test_db, default_org_id)
    source = ExecutionRun(
        project_id=project.id,
        run_type="draft_section",
        status="failed",
        input_json={"section_key": "technical-approach"},
    )
    test_db.add(source)
    test_db.commit()
    source_bridge = create_workflow_bridge_run(
        test_db,
        user,
        execution_run_id=source.id,
        project_id=project.id,
    )
    source_bridge.status = "failed"
    active_child = ExecutionRun(
        project_id=project.id,
        parent_execution_run_id=source.id,
        attempt_number=2,
        run_type="draft_section",
        status="queued",
        input_json={"section_key": "technical-approach"},
    )
    test_db.add(active_child)
    test_db.commit()
    child_bridge = create_workflow_bridge_run(
        test_db,
        user,
        execution_run_id=active_child.id,
        project_id=project.id,
        parent_run_id=source_bridge.id,
    )
    monkeypatch.setattr(
        "app.execution.service.check_workflow_quota",
        lambda *_args, **_kwargs: pytest.fail("active retry must not charge quota again"),
    )
    monkeypatch.setattr(
        "app.execution.service.request_task_outbox_dispatch",
        lambda *_args, **_kwargs: pytest.fail("active retry must not dispatch again"),
    )

    retried = retry_failed_run_command(test_db, source.id, user)

    assert retried.id == active_child.id
    assert retried.runtime_run_id == child_bridge.id
    assert test_db.query(ExecutionRun).filter_by(parent_execution_run_id=source.id).count() == 1


def test_retry_rejects_a_non_leaf_source_attempt(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    user = _user(default_org_id, default_user_id)
    project = _project(test_db, default_org_id)
    source = ExecutionRun(
        project_id=project.id,
        run_type="draft_section",
        status="failed",
        input_json={"section_key": "technical-approach"},
    )
    test_db.add(source)
    test_db.commit()
    source_bridge = create_workflow_bridge_run(
        test_db,
        user,
        execution_run_id=source.id,
        project_id=project.id,
    )
    source_bridge.status = "failed"
    test_db.add(
        ExecutionRun(
            project_id=project.id,
            parent_execution_run_id=source.id,
            attempt_number=2,
            run_type="draft_section",
            status="failed",
            input_json={"section_key": "technical-approach"},
        )
    )
    test_db.commit()

    with pytest.raises(HTTPException, match="A newer attempt already exists") as error:
        retry_failed_run_command(test_db, source.id, user)
    assert error.value.status_code == 409


def test_retry_rejects_a_deleted_byok_provider_instead_of_using_official_quota(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    user = _user(default_org_id, default_user_id)
    project = _project(test_db, default_org_id)
    config = ProviderConfig(
        user_id=user.id,
        provider_type="openai",
        api_key="x",
        model="test-model",
        label="Temporary provider",
    )
    source = ExecutionRun(
        project_id=project.id,
        run_type="draft_section",
        status="failed",
        input_json={"section_key": "technical-approach"},
    )
    test_db.add_all([config, source])
    test_db.commit()
    source_bridge = create_workflow_bridge_run(
        test_db,
        user,
        execution_run_id=source.id,
        project_id=project.id,
        provider_config_id=config.id,
    )
    source_bridge.status = "failed"
    test_db.commit()
    test_db.delete(config)
    test_db.commit()
    test_db.refresh(source_bridge)
    assert source_bridge.provider_config_id is None

    with pytest.raises(HTTPException, match="Original provider configuration") as error:
        retry_failed_run_command(test_db, source.id, user)
    assert error.value.status_code == 409


def test_retry_rejects_non_draft_or_non_terminal_runs(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    user = _user(default_org_id, default_user_id)
    project = _project(test_db, default_org_id)
    unsupported = ExecutionRun(
        project_id=project.id,
        run_type="ingest_bundle",
        status="failed",
        input_json={"bundle_id": "bundle-1"},
    )
    active = ExecutionRun(
        project_id=project.id,
        run_type="draft_section",
        status="running",
        input_json={"section_key": "technical-approach"},
    )
    test_db.add_all([unsupported, active])
    test_db.commit()

    with pytest.raises(HTTPException, match="Only draft workflows") as unsupported_error:
        retry_failed_run_command(test_db, unsupported.id, user)
    assert unsupported_error.value.status_code == 400

    with pytest.raises(HTTPException, match="Only failed or cancelled") as active_error:
        retry_failed_run_command(test_db, active.id, user)
    assert active_error.value.status_code == 400


def test_drafting_rejects_provider_configs_owned_by_another_user(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    project = _project(test_db, default_org_id)
    other_user = _other_user(test_db, default_org_id)
    config = ProviderConfig(
        user_id=other_user.id,
        provider_type="openai",
        api_key="x",
        model="test-model",
        label="Other member provider",
    )
    test_db.add(config)
    test_db.commit()

    with pytest.raises(HTTPException, match="Provider config not found") as error:
        draft_section_command(
            test_db,
            DraftSectionRequest(
                project_id=project.id,
                section_key="technical-approach",
                provider_config_id=config.id,
            ),
            _user(default_org_id, default_user_id),
        )
    assert error.value.status_code == 404


def test_retry_never_falls_back_to_another_member_byok_provider(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    project = _project(test_db, default_org_id)
    other_user = _other_user(test_db, default_org_id)
    config = ProviderConfig(
        user_id=other_user.id,
        provider_type="openai",
        api_key="x",
        model="test-model",
        label="Other member provider",
    )
    original = ExecutionRun(
        project_id=project.id,
        run_type="draft_section",
        status="failed",
        input_json={"section_key": "technical-approach"},
    )
    test_db.add_all([config, original])
    test_db.commit()
    source_user = CurrentUser(
        id=other_user.id,
        email=other_user.email,
        display_name=other_user.display_name,
        role="admin",
        org_id=default_org_id,
    )
    bridge = create_workflow_bridge_run(
        test_db,
        source_user,
        execution_run_id=original.id,
        project_id=project.id,
        provider_config_id=config.id,
    )
    bridge.status = "failed"
    test_db.commit()

    with pytest.raises(HTTPException, match="Original provider configuration") as error:
        retry_failed_run_command(test_db, original.id, _user(default_org_id, default_user_id))
    assert error.value.status_code == 409
