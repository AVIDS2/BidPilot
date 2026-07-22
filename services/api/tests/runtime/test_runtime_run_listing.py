"""Authorization and public-contract coverage for the aggregate Run Center."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.schemas import CurrentUser
from app.db import Base
from app.models import Organization, Project, ProjectMember, RuntimeEvent, RuntimeRun, User
from app.runtime.service import create_runtime_run, list_runtime_runs_query


def _current(user: User) -> CurrentUser:
    return CurrentUser(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
        org_id=user.org_id,
        org_slug="run-center",
    )


def _run(
    *,
    run_id: str,
    org_id: str,
    user_id: str,
    project_id: str | None = None,
) -> RuntimeRun:
    return RuntimeRun(
        id=run_id,
        kind="assistant_turn",
        status="running",
        org_id=org_id,
        user_id=user_id,
        project_id=project_id,
        engine="test-runtime",
        trace_id=f"trace-{run_id}",
    )


@pytest.fixture()
def runtime_listing_db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_run_center_list_respects_project_and_user_scope(runtime_listing_db: Session) -> None:
    org = Organization(id="org-run-center", slug="run-center", name="Run Center")
    member = User(
        id="user-member",
        org_id=org.id,
        email="member@run-center.test",
        display_name="Member",
        password_hash="test-only",
        role="member",
        email_verified=True,
    )
    other = User(
        id="user-other",
        org_id=org.id,
        email="other@run-center.test",
        display_name="Other",
        password_hash="test-only",
        role="member",
        email_verified=True,
    )
    admin = User(
        id="user-admin",
        org_id=org.id,
        email="admin@run-center.test",
        display_name="Admin",
        password_hash="test-only",
        role="admin",
        email_verified=True,
    )
    visible_project = Project(
        id="project-visible",
        org_id=org.id,
        slug="visible-run-center",
        name="Visible proposal",
        scenario_package="bidpilot",
    )
    hidden_project = Project(
        id="project-hidden",
        org_id=org.id,
        slug="hidden-run-center",
        name="Hidden proposal",
        scenario_package="bidpilot",
    )
    deleted_project = Project(
        id="project-deleted",
        org_id=org.id,
        slug="deleted-run-center",
        name="Deleted proposal",
        scenario_package="bidpilot",
        status="deleted",
    )
    visible_project_run = _run(
        run_id="run-visible-project",
        org_id=org.id,
        user_id=member.id,
        project_id=visible_project.id,
    )
    hidden_project_run = _run(
        run_id="run-hidden-project",
        org_id=org.id,
        user_id=other.id,
        project_id=hidden_project.id,
    )
    own_global_run = _run(run_id="run-own-global", org_id=org.id, user_id=member.id)
    other_global_run = _run(run_id="run-other-global", org_id=org.id, user_id=other.id)
    deleted_project_run = _run(
        run_id="run-deleted-project",
        org_id=org.id,
        user_id=other.id,
        project_id=deleted_project.id,
    )

    runtime_listing_db.add_all(
        [
            org,
            member,
            other,
            admin,
            visible_project,
            hidden_project,
            deleted_project,
            ProjectMember(project_id=visible_project.id, user_id=member.id, role="viewer"),
            visible_project_run,
            hidden_project_run,
            own_global_run,
            other_global_run,
            deleted_project_run,
            RuntimeEvent(
                run_id=visible_project_run.id,
                sequence=1,
                event_type="run.started",
                public_summary="准备读取资料。",
                payload_json={},
                schema_version="1.0",
            ),
            RuntimeEvent(
                run_id=visible_project_run.id,
                sequence=2,
                event_type="capability.succeeded",
                public_summary="已读取资料。",
                payload_json={},
                schema_version="1.0",
            ),
        ]
    )
    runtime_listing_db.commit()

    member_rows = list_runtime_runs_query(runtime_listing_db, _current(member), limit=50)
    member_by_id = {item.run.id: item for item in member_rows}

    assert set(member_by_id) == {visible_project_run.id, own_global_run.id}
    assert member_by_id[visible_project_run.id].project_name == "Visible proposal"
    assert member_by_id[visible_project_run.id].latest_event_summary == "已读取资料。"

    admin_rows = list_runtime_runs_query(runtime_listing_db, _current(admin), limit=50)
    assert {item.run.id for item in admin_rows} == {
        visible_project_run.id,
        hidden_project_run.id,
        own_global_run.id,
        other_global_run.id,
    }
    assert deleted_project_run.id not in {item.run.id for item in admin_rows}


def test_runtime_run_list_endpoint_exposes_only_public_fields(
    client,
    test_db: Session,
    default_org_id: str,
    default_user_id: str,
) -> None:
    user = CurrentUser(
        id=default_user_id,
        email="dev@docpilot.local",
        display_name="Dev User",
        role="admin",
        org_id=default_org_id,
    )
    run = create_runtime_run(
        test_db,
        user,
        kind="assistant_turn",
        engine="deterministic",
        input_json={"message": "不应出现在列表中"},
    )

    response = client.get("/runtime/runs?limit=10")

    assert response.status_code == 200
    item = next(candidate for candidate in response.json() if candidate["id"] == run.id)
    assert item["kind"] == "assistant_turn"
    assert item["latest_event_summary"] == "任务已开始。"
    assert "trace_id" not in item
    assert "input_json" not in item
    assert "result_json" not in item
    assert "policy_snapshot_json" not in item
