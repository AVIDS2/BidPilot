"""Durable attachment staging and governed project-ingestion tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

import pytest
from fastapi import HTTPException
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.assistant.attachments import (
    attach_staged_attachments_to_project,
    attachment_planner_context,
    extract_attachment_text,
    hydrate_assistant_attachments,
    stage_assistant_attachment,
)
from app.assistant.schemas import AssistantAttachmentPayload
from app.auth.schemas import CurrentUser
from app.documents.service import upload_document_command
from app.models import AssistantAttachment, Bundle, Project, ProjectMember, RuntimeRun, SourceDocument
from app.runtime.operator_graph import OperatorPlan, OperatorPlanningContext, build_operator_graph
from app.runtime.service import create_runtime_run


def _user(default_org_id: str, default_user_id: str) -> CurrentUser:
    return CurrentUser(
        id=default_user_id,
        email="dev@docpilot.local",
        display_name="Dev User",
        role="admin",
        org_id=default_org_id,
    )


def _project_for_user(test_db, default_org_id: str, default_user_id: str) -> Project:
    suffix = uuid.uuid4().hex[:8]
    project = Project(
        org_id=default_org_id,
        slug=f"assistant-attachment-{suffix}",
        name=f"Assistant Attachment {suffix}",
        scenario_package="bidpilot",
    )
    test_db.add(project)
    test_db.flush()
    test_db.add(ProjectMember(project_id=project.id, user_id=default_user_id, role="owner"))
    test_db.commit()
    test_db.refresh(project)
    return project


def _stage_text_attachment(test_db, user: CurrentUser, monkeypatch) -> tuple[AssistantAttachment, bytes]:
    data = "强制项：提供近三年类似项目业绩。".encode()
    extraction = extract_attachment_text(
        filename="requirements.txt",
        content_type="text/plain",
        data=data,
    )
    monkeypatch.setattr(
        "app.adapters.storage.upload_assistant_staging_bytes",
        lambda **kwargs: f"docpilot-assistant-staging/assistant-attachments/{kwargs['attachment_id']}",
    )
    staged = stage_assistant_attachment(
        test_db,
        current_user=user,
        filename="requirements.txt",
        content_type="text/plain",
        data=data,
        kind="file",
        extraction=extraction,
    )
    record = test_db.get(AssistantAttachment, staged.id)
    assert record is not None
    return record, data


def test_staged_attachment_hydrates_server_text_and_rejects_foreign_owner(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    user = _user(default_org_id, default_user_id)
    record, _ = _stage_text_attachment(test_db, user, monkeypatch)

    hydrated = hydrate_assistant_attachments(
        test_db,
        current_user=user,
        attachments=[
            AssistantAttachmentPayload(
                id=record.id,
                name="browser-spoofed-name.txt",
                extracted_text="浏览器不应当决定这段正文",
            )
        ],
    )

    assert hydrated[0].name == "requirements.txt"
    assert "近三年类似项目业绩" in (hydrated[0].extracted_text or "")
    assert attachment_planner_context(hydrated) == [
        {
            "id": record.id,
            "name": "requirements.txt",
            "kind": "file",
            "mime_type": "text/plain",
            "size": record.size,
        }
    ]

    foreign_user = user.model_copy(update={"id": "another-user"})
    with pytest.raises(HTTPException) as exc_info:
        hydrate_assistant_attachments(
            test_db,
            current_user=foreign_user,
            attachments=[AssistantAttachmentPayload(id=record.id, name="requirements.txt")],
        )
    assert exc_info.value.status_code == 404


def test_attachment_upload_response_never_returns_extracted_document_text(
    client,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    """The browser receives attachment metadata only; text stays server-side."""
    data = "强制项：提供近三年类似项目业绩。".encode()
    monkeypatch.setattr(
        "app.adapters.storage.upload_assistant_staging_bytes",
        lambda **kwargs: f"docpilot-assistant-staging/assistant-attachments/{kwargs['attachment_id']}",
    )

    response = client.post(
        "/assistant/attachments?kind=file",
        files={"file": ("requirements.txt", data, "text/plain")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["extracted_text"] == ""
    assert "近三年类似项目业绩" not in response.text


def test_staging_commit_failure_removes_private_object(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    """A failed database commit must not leave an unreachable staged object behind."""
    user = _user(default_org_id, default_user_id)
    data = b"staging cleanup test"
    extraction = extract_attachment_text(
        filename="requirements.txt",
        content_type="text/plain",
        data=data,
    )
    deleted: list[str] = []
    monkeypatch.setattr(
        "app.adapters.storage.upload_assistant_staging_bytes",
        lambda **_kwargs: "docpilot-assistant-staging/assistant-attachments/test-object",
    )
    monkeypatch.setattr("app.adapters.storage.delete_storage_key", lambda key: deleted.append(key))
    monkeypatch.setattr(test_db, "commit", lambda: (_ for _ in ()).throw(RuntimeError("database unavailable")))

    with pytest.raises(HTTPException) as exc_info:
        stage_assistant_attachment(
            test_db,
            current_user=user,
            filename="requirements.txt",
            content_type="text/plain",
            data=data,
            kind="file",
            extraction=extraction,
        )

    assert exc_info.value.status_code == 503
    assert deleted == ["docpilot-assistant-staging/assistant-attachments/test-object"]


def test_attachment_ingestion_copies_to_project_then_queues_worker(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    user = _user(default_org_id, default_user_id)
    project = _project_for_user(test_db, default_org_id, default_user_id)
    record, data = _stage_text_attachment(test_db, user, monkeypatch)
    staging_key = record.storage_key
    copied: list[tuple[str, str, bytes, str]] = []
    deleted: list[str] = []
    queued: list[tuple[str, list[str]]] = []

    monkeypatch.setattr("app.adapters.storage.download_storage_key", lambda _key: data)
    monkeypatch.setattr(
        "app.adapters.storage.upload_bytes",
        lambda project_id, object_name, body, content_type: copied.append((project_id, object_name, body, content_type))
        or f"docpilot-{project_id}/{object_name}",
    )
    monkeypatch.setattr("app.adapters.storage.delete_storage_key", lambda key: deleted.append(key))
    monkeypatch.setattr(
        "app.assistant.attachments.celery.send_task",
        lambda task, args: queued.append((task, args)),
    )

    result = attach_staged_attachments_to_project(
        test_db,
        current_user=user,
        project_id=project.id,
        attachment_ids=[record.id],
    )

    test_db.refresh(record)
    document = test_db.get(SourceDocument, record.document_id)
    bundle = test_db.get(Bundle, record.bundle_id)
    assert result["attachment_count"] == 1
    assert result["ingest_queued"] is True
    assert record.status == "attached"
    assert record.project_id == project.id
    assert document is not None and document.original_filename == "requirements.txt"
    assert bundle is not None and bundle.ingest_status == "queued"
    assert copied and copied[0][0] == project.id
    assert queued == [("worker.ingest_bundle", [bundle.id])]
    assert deleted == [staging_key]
    assert record.storage_key == ""

    with pytest.raises(HTTPException) as exc_info:
        attach_staged_attachments_to_project(
            test_db,
            current_user=user,
            project_id=project.id,
            attachment_ids=[record.id],
        )
    assert exc_info.value.status_code == 409


def test_browser_document_upload_consumes_matching_staged_attachment(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    user = _user(default_org_id, default_user_id)
    project = _project_for_user(test_db, default_org_id, default_user_id)
    bundle = Bundle(project_id=project.id, label="UI 上传", source_type="manual", ingest_status="awaiting_upload")
    test_db.add(bundle)
    test_db.commit()
    test_db.refresh(bundle)
    record, data = _stage_text_attachment(test_db, user, monkeypatch)
    staging_key = record.storage_key
    deleted: list[str] = []

    monkeypatch.setattr(
        "app.adapters.storage.upload_bytes",
        lambda project_id, object_name, body, content_type: f"docpilot-{project_id}/{object_name}",
    )
    monkeypatch.setattr("app.adapters.storage.delete_storage_key", lambda key: deleted.append(key))

    uploaded = upload_document_command(
        test_db,
        bundle_id=bundle.id,
        filename="requirements.txt",
        content_type="text/plain",
        data=data,
        current_user=user,
        assistant_attachment_id=record.id,
    )

    test_db.refresh(record)
    assert record.status == "attached"
    assert record.document_id == uploaded.id
    assert deleted == [staging_key]
    assert record.storage_key == ""


def test_expired_staged_attachment_is_not_usable(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    user = _user(default_org_id, default_user_id)
    record, _ = _stage_text_attachment(test_db, user, monkeypatch)
    record.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
    test_db.commit()

    with pytest.raises(HTTPException) as exc_info:
        hydrate_assistant_attachments(
            test_db,
            current_user=user,
            attachments=[AssistantAttachmentPayload(id=record.id, name="requirements.txt")],
        )
    assert exc_info.value.status_code == 410


def test_harness_stream_hydrates_attachment_metadata_before_model_turn(
    client,
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    user = _user(default_org_id, default_user_id)
    record, _ = _stage_text_attachment(test_db, user, monkeypatch)
    monkeypatch.setenv("DOCPILOT_ASSISTANT_ENGINE", "harness")

    class Response:
        content = "已收到附件。"
        tool_calls: list[dict] = []
        usage_metadata = None

    class CapturingHarnessLLM:
        def __init__(self) -> None:
            self.calls: list[list[object]] = []

        def bind_tools(self, _tools):
            return self

        def invoke(self, messages):
            self.calls.append(list(messages))
            return Response()

    llm = CapturingHarnessLLM()
    monkeypatch.setattr("app.runtime.operator_adapter.get_agent_llm", lambda **_kwargs: llm)
    monkeypatch.setattr("app.runtime.operator_adapter._load_authorized_memory_context", lambda *_args, **_kwargs: None)

    response = client.post(
        "/assistant/stream",
        json={
            "message": "先看看这份附件",
            "attachments": [
                {
                    "id": record.id,
                    "name": "browser-spoofed-name.txt",
                    "mime_type": "application/octet-stream",
                    "extracted_text": "浏览器伪造正文",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert "浏览器伪造正文" not in response.text
    assert llm.calls
    prompt = "\n".join(str(getattr(message, "content", "")) for message in llm.calls[0])
    assert "requirements.txt (file, text/plain" in prompt
    assert "强制项：提供近三年类似项目业绩。" in prompt
    assert "browser-spoofed-name.txt" not in prompt
    assert "浏览器伪造正文" not in prompt


def test_operator_preserves_staged_attachment_through_governed_project_setup(
    test_db,
    default_org_id: str,
    default_user_id: str,
    monkeypatch,
) -> None:
    """The full Agent path must not lose an uploaded file between approvals."""
    user = _user(default_org_id, default_user_id)
    record, data = _stage_text_attachment(test_db, user, monkeypatch)
    project_name = f"Attachment Agent Project {uuid.uuid4().hex[:8]}"
    planner_contexts: list[OperatorPlanningContext] = []

    monkeypatch.setattr("app.assistant.tools.check_plan_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("app.adapters.storage.download_storage_key", lambda _key: data)
    monkeypatch.setattr(
        "app.adapters.storage.upload_bytes",
        lambda project_id, object_name, body, content_type: f"docpilot-{project_id}/{object_name}",
    )
    monkeypatch.setattr("app.adapters.storage.delete_storage_key", lambda _key: None)
    monkeypatch.setattr("app.assistant.attachments.celery.send_task", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "app.readiness.service.upload_bytes",
        lambda project_id, object_name, body, content_type: f"docpilot-{project_id}/{object_name}",
    )

    def planner(context: OperatorPlanningContext) -> OperatorPlan:
        planner_contexts.append(context)
        assert context.available_attachments == (
            {
                "id": record.id,
                "name": "requirements.txt",
                "kind": "file",
                "mime_type": "text/plain",
                "size": record.size,
            },
        )
        if context.calls_made == 0:
            return OperatorPlan(
                mode="tool",
                capability_name="create_project",
                arguments={"name": project_name, "scenario_package": "bidpilot"},
                continue_after_tool=True,
            )
        if context.calls_made == 1:
            project_id = str((context.last_result or {}).get("payload", {}).get("id") or "")
            assert project_id
            return OperatorPlan(
                mode="tool",
                capability_name="attach_uploaded_documents",
                arguments={"project_id": project_id, "attachment_ids": [record.id]},
                continue_after_tool=True,
            )
        project_id = context.active_project_id
        assert project_id
        return OperatorPlan(
            mode="tool",
            capability_name="generate_readiness_pack",
            arguments={"project_id": project_id},
        )

    run = create_runtime_run(
        test_db,
        user,
        kind="assistant_turn",
        engine="langgraph_operator",
        input_json={"message": "创建项目并处理附件", "attachment_ids": [record.id]},
    )
    graph = build_operator_graph(test_db, user, planner=planner, checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": run.id}}

    first = graph.invoke(
        {
            "runtime_run_id": run.id,
            "user_message": "创建项目并把附件加入资料包",
            "calls_made": 0,
            "available_attachments": attachment_planner_context(
                hydrate_assistant_attachments(
                    test_db,
                    current_user=user,
                    attachments=[AssistantAttachmentPayload(id=record.id, name=record.original_filename)],
                )
            ),
        },
        config=config,
    )
    assert first.get("__interrupt__")

    second = graph.invoke(Command(resume={"decision": "approve"}), config=config)
    assert second.get("__interrupt__")

    third = graph.invoke(Command(resume={"decision": "approve"}), config=config)
    assert third.get("__interrupt__")

    finished = graph.invoke(Command(resume={"decision": "approve"}), config=config)
    assert "投标准备度包已生成" in finished["final_message"]
    assert len(planner_contexts) == 3
    assert finished["last_result"]["payload"]["xlsx_download_path"].endswith("/xlsx")
    assert finished["last_result"]["payload"]["docx_download_path"].endswith("/docx")

    test_db.refresh(record)
    run = test_db.get(RuntimeRun, run.id)
    assert record.status == "attached"
    assert test_db.query(Project).filter_by(name=project_name).count() == 1
    assert test_db.get(SourceDocument, record.document_id) is not None
    assert run is not None and run.status == "succeeded"
