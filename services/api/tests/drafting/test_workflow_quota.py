import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.schemas import CurrentUser
from app.auth.service import _hash_password
from app.db import Base, get_db
from app.main import app
from app.drafting.schemas import ResumeRunRequest
from app.drafting.service import resume_run_command
from app.models import (
    ExecutionRun,
    Organization,
    OrganizationMembership,
    Project,
    ProjectMember,
    Subscription,
    TaskOutboxEvent,
    User,
    UsageEvent,
)
from app.runtime.service import create_workflow_bridge_run
from app.usage.schemas import ProviderSource
from app.usage.service import record_usage_event


def _make_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with SessionLocal() as session:
        session.add(
            Organization(
                id="00000000-0000-0000-0000-000000000001",
                slug="default",
                name="Default Organization",
            )
        )
        session.commit()
    return SessionLocal


def _make_user_project(SessionLocal, plan: str = "starter"):
    db = SessionLocal()
    org = Organization(slug=f"quota-{uuid.uuid4().hex[:8]}", name="Quota Org")
    db.add(org)
    db.flush()
    user = User(
        email=f"quota-{uuid.uuid4().hex[:8]}@example.com",
        display_name="Quota User",
        password_hash=_hash_password("Test1234"),
        role="member",
        email_verified=True,
        org_id=org.id,
    )
    db.add(user)
    db.flush()
    db.add(OrganizationMembership(org_id=org.id, user_id=user.id, role="owner"))
    db.add(Subscription(user_id=user.id, plan=plan, status="active"))
    project = Project(
        org_id=org.id,
        slug=f"quota-project-{uuid.uuid4().hex[:8]}",
        name="Quota Project",
        scenario_package="bidpilot",
    )
    db.add(project)
    db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=user.id, role="contributor"))
    db.commit()
    db.refresh(user)
    db.refresh(project)
    return db, user, project


def _override_user(user):
    async def dependency():
        return CurrentUser(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            plan="starter",
            org_id=user.org_id,
            org_slug="",
            email_verified=True,
            disabled=False,
        )

    return dependency


def _override_get_db(sessionmaker_):
    def dependency():
        with sessionmaker_() as session:
            yield session

    return dependency


def test_draft_section_blocks_starter_fourth_official_run(client):
    SessionLocal = _make_db()
    db, user, project = _make_user_project(SessionLocal, "starter")
    try:
        for _ in range(3):
            record_usage_event(
                db,
                user_id=user.id,
                org_id=user.org_id,
                project_id=project.id,
                event_type="workflow_draft_started",
                provider_source=ProviderSource.OFFICIAL,
            )
        db.commit()

        from app.auth.service import require_auth

        app.dependency_overrides[get_db] = _override_get_db(SessionLocal)
        app.dependency_overrides[require_auth] = _override_user(user)
        response = client.post(
            "/drafting/sections",
            json={"project_id": project.id, "section_key": "technical-approach"},
        )
    finally:
        app.dependency_overrides.clear()
        db.close()

    assert response.status_code == 403
    assert "starter workflow trial limit" in response.text


def test_draft_section_records_usage_and_commits_outbox_before_wake(client, monkeypatch):
    SessionLocal = _make_db()
    db, user, project = _make_user_project(SessionLocal, "starter")
    try:
        from app.auth.service import require_auth

        app.dependency_overrides[get_db] = _override_get_db(SessionLocal)
        app.dependency_overrides[require_auth] = _override_user(user)
        observed: list[str] = []

        def observe_post_commit(event_id: str) -> bool:
            with SessionLocal() as fresh_db:
                event = fresh_db.get(TaskOutboxEvent, event_id)
                assert event is not None
                assert event.status == "pending"
                assert event.task_name == "worker.draft_section"
                assert fresh_db.get(ExecutionRun, event.execution_run_id) is not None
            observed.append(event_id)
            return True

        monkeypatch.setattr("app.drafting.service.request_task_outbox_dispatch", observe_post_commit)
        response = client.post(
            "/drafting/sections",
            json={"project_id": project.id, "section_key": "technical-approach"},
        )
        assert response.status_code == 202
        assert len(observed) == 1

        db.expire_all()
        events = db.query(UsageEvent).filter_by(user_id=user.id, event_type="workflow_draft_started").all()
        assert len(events) == 1
        assert events[0].provider_source == "official"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_resume_workflow_uses_sequenced_outbox_and_rejects_duplicate_resume(monkeypatch):
    SessionLocal = _make_db()
    db, user, project = _make_user_project(SessionLocal, "starter")
    try:
        current_user = CurrentUser(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            plan="starter",
            org_id=user.org_id,
            org_slug="",
            email_verified=True,
            disabled=False,
        )
        run = ExecutionRun(
            project_id=project.id,
            run_type="draft_section",
            status="awaiting_human",
            input_json={"section_key": "technical-approach"},
        )
        db.add(run)
        db.flush()
        runtime_run = create_workflow_bridge_run(
            db,
            current_user,
            execution_run_id=run.id,
            project_id=project.id,
        )
        run.input_json = {"section_key": "technical-approach", "runtime_run_id": runtime_run.id}
        db.commit()

        woken: list[str] = []
        monkeypatch.setattr("app.drafting.service.request_task_outbox_dispatch", lambda event_id: woken.append(event_id) or True)

        response = resume_run_command(
            db,
            run.id,
            ResumeRunRequest(decision="approved"),
            current_user,
        )

        db.refresh(run)
        event = db.query(TaskOutboxEvent).filter_by(execution_run_id=run.id).one()
        assert response.status == "running"
        assert run.input_json["resume_sequence"] == 1
        assert event.task_name == "worker.resume_draft"
        assert event.args_json == [run.id, "approved", None]
        assert event.deduplication_key == f"workflow-resume:{run.id}:1"
        assert woken == [event.id]

        try:
            resume_run_command(db, run.id, ResumeRunRequest(decision="approved"), current_user)
        except RuntimeError as exc:
            assert "not awaiting human approval" in str(exc)
        else:
            raise AssertionError("duplicate resume must be rejected after the first outbox event commits")
    finally:
        db.close()
