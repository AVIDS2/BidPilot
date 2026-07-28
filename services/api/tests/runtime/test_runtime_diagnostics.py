from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.auth.schemas import CurrentUser
from app.models import (
    AuditEvent,
    Deliverable,
    DeliverableSection,
    EvidenceSet,
    ExecutionRun,
    ModelUsageRecord,
    Organization,
    Project,
    RuntimeAction,
    RuntimeApproval,
    RuntimeEvent,
    RuntimeRun,
    SectionVersion,
    TaskOutboxEvent,
)
from app.runtime.diagnostics import get_runtime_diagnostics


def _id() -> str:
    return str(uuid.uuid4())


def _current(*, user_id: str, org_id: str) -> CurrentUser:
    return CurrentUser(
        id=user_id,
        email="ops@example.test",
        display_name="Ops",
        role="admin",
        org_id=org_id,
    )


def _seed_runtime_trace(test_db, default_org_id: str, default_user_id: str) -> RuntimeRun:
    now = datetime.now(UTC).replace(tzinfo=None)
    project = Project(
        id=_id(),
        org_id=default_org_id,
        slug=f"runtime-diagnostics-{uuid.uuid4().hex[:8]}",
        name="Runtime diagnostics fixture",
        scenario_package="bidpilot",
    )
    execution = ExecutionRun(
        id=_id(),
        project_id=project.id,
        run_type="draft_section",
        status="failed",
        attempt_number=2,
        started_at=now - timedelta(seconds=8),
        finished_at=now - timedelta(seconds=1),
    )
    run = RuntimeRun(
        id=_id(),
        kind="assistant_turn",
        status="failed",
        org_id=default_org_id,
        user_id=default_user_id,
        project_id=project.id,
        execution_run_id=execution.id,
        engine="streaming_harness",
        trace_id=f"trace-{uuid.uuid4().hex}",
        idempotency_key=f"request-{uuid.uuid4().hex}",
        provider_config_id=None,
        model="deepseek-v4-flash",
        reasoning_effort="high",
        input_json={"provider_source": "official", "api_key": "sk-must-not-leak"},
        error_code="provider_timeout",
        started_at=now - timedelta(seconds=10),
        finished_at=now,
    )
    action = RuntimeAction(
        id=_id(),
        run_id=run.id,
        action_key="trace-action",
        capability_name="start_draft_section",
        status="failed",
        risk_level="write",
        policy_outcome="allowed",
        approval_mode="risky_only",
        arguments_json={"api_key": "sk-must-not-leak", "section_key": "technical"},
        result_json={"provider_response": "must-not-leak"},
        public_summary="模型回复中的业务文本 must-not-leak",
        error_code="provider_timeout",
        error_message="provider secret must-not-leak",
        created_at=now - timedelta(seconds=9),
        completed_at=now,
    )
    approval = RuntimeApproval(
        id=_id(),
        action_id=action.id,
        user_id=default_user_id,
        org_id=default_org_id,
        status="approved",
        payload_json={"arguments": {"api_key": "sk-must-not-leak"}},
        decision_json={"decision": "approve"},
        created_at=now - timedelta(seconds=8),
        expires_at=now + timedelta(minutes=5),
        resolved_at=now - timedelta(seconds=7),
    )
    event = RuntimeEvent(
        id=_id(),
        run_id=run.id,
        sequence=1,
        event_type="capability.succeeded",
        public_summary="检索摘要中的业务文本 must-not-leak",
        payload_json={
            "capability": "knowledge_retriever",
            "evidence_count": 2,
            "retrieval_candidate_count": 2,
            "retrieval_fused_candidate_count": 7,
            "retrieval_reranked_candidate_count": 4,
            "retrieval_latency_ms": 19,
            "api_key": "sk-must-not-leak",
        },
        created_at=now - timedelta(seconds=6),
    )
    task = TaskOutboxEvent(
        id=_id(),
        org_id=default_org_id,
        project_id=project.id,
        execution_run_id=execution.id,
        runtime_run_id=run.id,
        task_name="run_section_workflow",
        args_json=["sk-must-not-leak"],
        kwargs_json={"api_key": "sk-must-not-leak"},
        deduplication_key=f"diagnostics-{uuid.uuid4().hex}",
        status="failed",
        dispatch_attempts=2,
        delivery_attempts=2,
        last_error_code="worker_timeout",
        created_at=now - timedelta(seconds=8),
        dispatched_at=now - timedelta(seconds=7),
        completed_at=now - timedelta(seconds=2),
    )
    usage = ModelUsageRecord(
        id=_id(),
        org_id=default_org_id,
        user_id=default_user_id,
        project_id=project.id,
        execution_run_id=execution.id,
        runtime_run_id=run.id,
        provider_source="official",
        provider_type="openai",
        model_name="deepseek-v4-flash",
        workload="workflow_drafting",
        input_tokens=120,
        output_tokens=80,
        reasoning_tokens=20,
        total_tokens=220,
    )
    evidence_set = EvidenceSet(
        id=_id(),
        project_id=project.id,
        execution_run_id=execution.id,
        section_key="technical",
        query_text="not exposed outside retrieval",
        status="degraded",
        degraded_reasons_json=["embedding_unavailable"],
    )
    deliverable = Deliverable(
        id=_id(),
        project_id=project.id,
        type="proposal",
        title="Bid response",
    )
    section = DeliverableSection(
        id=_id(),
        deliverable_id=deliverable.id,
        section_key="technical",
        title="Technical response",
        sort_order=1,
    )
    version = SectionVersion(
        id=_id(),
        deliverable_section_id=section.id,
        version_number=1,
        content_markdown="must not leave diagnostics",
        generation_run_id=execution.id,
    )
    audit = AuditEvent(
        id=_id(),
        project_id=project.id,
        actor_type="user",
        actor_id=default_user_id,
        event_type="runtime.capability.failed",
        payload_json={
            "runtime_run_id": run.id,
            "trace_id": run.trace_id,
            "runtime_action_id": action.id,
            "api_key": "sk-must-not-leak",
        },
    )
    # The contract models intentionally avoid broad ORM relationships. Flush in
    # real dependency order so this fixture exercises PostgreSQL constraints
    # instead of relying on SQLAlchemy insert ordering.
    test_db.add(project)
    test_db.flush()
    test_db.add_all([execution, deliverable])
    test_db.flush()
    test_db.add_all([run, section])
    test_db.flush()
    test_db.add_all([action, task, usage, evidence_set, version])
    test_db.flush()
    test_db.add_all([approval, event, audit])
    test_db.commit()
    return run


def test_admin_runtime_diagnostics_are_correlated_and_redacted(
    client: TestClient,
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    run = _seed_runtime_trace(test_db, default_org_id, default_user_id)

    response = client.get(f"/ops/runtime-runs/{run.id}/diagnostics")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["run_id"] == run.id
    assert body["user_ref"].startswith("user_")
    assert body["org_ref"].startswith("org_")
    assert body["request_ref"].startswith("request_")
    assert body["error_code"] == "provider_timeout"
    assert body["failure_category"] == "provider"
    assert body["retries"] == {
        "execution_retries": 1,
        "provider_retries": 0,
        "task_redeliveries": 2,
        "total": 3,
    }
    assert body["model_usage"][0]["total_tokens"] == 220
    assert body["model_usage"][0]["cost_status"] == "provider_cost_not_reported"
    assert body["cost_status"] == "provider_cost_not_reported"
    assert body["retrieval"] == {
        "retrieval_attempt_count": 1,
        "candidate_count": 2,
        "fused_candidate_count": 7,
        "reranked_candidate_count": 4,
        "evidence_hit_count": 2,
        "evidence_set_count": 1,
        "retrieval_latency_ms": 19,
        "degraded_evidence_set_count": 1,
    }
    assert body["audit_events"][0]["event_type"] == "runtime.capability.failed"
    assert body["deliverables"][0]["section_version_id"]
    assert body["actions"][0]["public_summary"] == "操作未完成。"
    assert body["events"][0]["public_summary"] == "能力步骤已完成。"
    assert "provider_cost_not_reported" in body["alert_codes"]
    assert "runtime_failed_provider" in body["alert_codes"]
    assert "sk-must-not-leak" not in response.text
    assert "must not leave diagnostics" not in response.text
    assert "模型回复中的业务文本" not in response.text
    assert "检索摘要中的业务文本" not in response.text


def test_runtime_diagnostics_hide_cross_organization_run(
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    run = _seed_runtime_trace(test_db, default_org_id, default_user_id)
    other_org = Organization(id=_id(), slug=f"other-{uuid.uuid4().hex[:8]}", name="Other")
    test_db.add(other_org)
    test_db.commit()

    with pytest.raises(HTTPException) as exc_info:
        get_runtime_diagnostics(
            test_db,
            current_user=_current(user_id="other-admin", org_id=other_org.id),
            run_id=run.id,
        )

    assert exc_info.value.status_code == 404


def test_runtime_diagnostics_resolve_project_created_by_global_run(
    client: TestClient,
    test_db,
    default_org_id: str,
    default_user_id: str,
) -> None:
    project = Project(
        id=_id(),
        org_id=default_org_id,
        slug=f"created-by-run-{uuid.uuid4().hex[:8]}",
        name="Created by runtime",
        scenario_package="bidpilot",
    )
    test_db.add(project)
    test_db.flush()
    run = RuntimeRun(
        id=_id(),
        kind="assistant_turn",
        status="succeeded",
        org_id=default_org_id,
        user_id=default_user_id,
        engine="streaming_harness",
        trace_id=f"trace-{uuid.uuid4().hex}",
    )
    action = RuntimeAction(
        id=_id(),
        run_id=run.id,
        action_key="created-project",
        capability_name="create_project",
        status="succeeded",
        risk_level="write",
        policy_outcome="allowed",
        approval_mode="risky_only",
        result_json={"id": project.id, "name": "not exposed"},
    )
    audit = AuditEvent(
        id=_id(),
        project_id=project.id,
        actor_type="user",
        actor_id=default_user_id,
        event_type="runtime.capability.succeeded",
        payload_json={"runtime_run_id": run.id, "trace_id": run.trace_id},
    )
    test_db.add(run)
    test_db.flush()
    test_db.add_all([action, audit])
    test_db.commit()

    response = client.get(f"/ops/runtime-runs/{run.id}/diagnostics")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["project_id"] == project.id
    assert len(body["audit_events"]) == 1
    assert body["audit_events"][0]["event_id"] == audit.id
    assert body["audit_events"][0]["event_type"] == "runtime.capability.succeeded"
