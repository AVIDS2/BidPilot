"""Typed platform tools exposed to the assistant harness."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.auth.service import check_plan_limit
from app.bundles.service import list_bundles_query
from app.deliverables.schemas import DeliverableCreate
from app.deliverables.service import create_deliverable_command, list_deliverables_query
from app.documents.service import list_documents_query
from app.drafting.schemas import DraftSectionRequest, RedraftSectionRequest
from app.drafting.service import draft_section_command, redraft_section_command
from app.evidence.service import list_evidence_query
from app.execution.service import list_runs_query, retry_failed_run_command
from app.models import Deliverable, DeliverableSection, Project, ReviewThread
from app.projects.schemas import ProjectCreate
from app.projects.service import create_project_command
from app.requirements.service import list_requirements_query
from app.versions.service import list_versions_query

from .schemas import AssistantToolResult


def execute_tool(
    db: Session,
    user: CurrentUser,
    tool_name: str,
    arguments: dict,
) -> AssistantToolResult:
    if tool_name == "search_projects":
        return search_projects(db, user, arguments)
    if tool_name == "create_project":
        return create_project(db, user, arguments)
    if tool_name == "get_project_summary":
        return get_project_summary(db, user, arguments)
    if tool_name == "list_project_bundles":
        return list_project_bundles(db, user, arguments)
    if tool_name == "list_sections":
        return list_sections(db, user, arguments)
    if tool_name == "list_pending_reviews":
        return list_pending_reviews(db, user, arguments)
    if tool_name == "open_page":
        return open_page(arguments)
    if tool_name == "get_runtime_status":
        return get_runtime_status(db, user, arguments)
    if tool_name == "start_draft_section":
        return start_draft_section(db, user, arguments)
    if tool_name == "start_redraft_section":
        return start_redraft_section(db, user, arguments)
    if tool_name == "list_requirements":
        return list_requirements_tool(db, user, arguments)
    if tool_name == "list_evidence":
        return list_evidence_tool(db, user, arguments)
    if tool_name == "list_deliverables":
        return list_deliverables_tool(db, user, arguments)
    if tool_name == "list_documents":
        return list_documents_tool(db, user, arguments)
    if tool_name == "get_section_versions":
        return get_section_versions_tool(db, user, arguments)
    if tool_name == "create_deliverable":
        return create_deliverable_tool(db, user, arguments)
    if tool_name == "retry_run":
        return retry_run_tool(db, user, arguments)
    if tool_name == "export_deliverable":
        return export_deliverable_tool(db, user, arguments)
    if tool_name == "delete_project":
        return delete_project_tool(db, user, arguments)
    if tool_name == "upload_document":
        return upload_document_stub(arguments)
    raise ValueError(f"Unsupported assistant tool: {tool_name}")


def search_projects(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    query = (arguments.get("query") or "").strip()
    stmt = select(Project).where(Project.org_id == (user.org_id or "default"))
    if query:
        stmt = stmt.where(Project.name.ilike(f"%{query}%"))
    projects = db.scalars(stmt.order_by(Project.created_at.desc()).limit(10)).all()
    result = {
        "items": [
            {
                "id": project.id,
                "name": project.name,
                "status": project.status,
                "scenario_package": project.scenario_package,
            }
            for project in projects
        ]
    }
    return AssistantToolResult(
        tool_name="search_projects",
        result=result,
        summary=f"找到 {len(projects)} 个项目。",
    )


def create_project(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    name = str(arguments.get("name") or "").strip()
    if not name:
        raise ValueError("Project name is required")

    check_plan_limit(db, user.id, "projects", delta=1, plan=user.plan)
    project = create_project_command(
        db,
        ProjectCreate(
            name=name,
            scenario_package=arguments.get("scenario_package") or "bidpilot",
        ),
        user.org_id or "default",
    )
    return AssistantToolResult(
        tool_name="create_project",
        result=project.model_dump(),
        summary=f"项目「{project.name}」已创建。",
    )


def get_project_summary(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project = _get_project_for_user(db, user, arguments["project_id"])
    result = {
        "id": project.id,
        "name": project.name,
        "status": project.status,
        "scenario_package": project.scenario_package,
    }
    return AssistantToolResult(
        tool_name="get_project_summary",
        result=result,
        summary=f"项目「{project.name}」当前状态是 {project.status}。",
    )


def list_project_bundles(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project = _get_project_for_user(db, user, arguments["project_id"])
    bundles = list_bundles_query(db, project.id)
    return AssistantToolResult(
        tool_name="list_project_bundles",
        result={"items": [bundle.model_dump() for bundle in bundles]},
        summary=f"项目「{project.name}」下有 {len(bundles)} 个资料包。",
    )


def list_sections(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project = _get_project_for_user(db, user, arguments["project_id"])
    rows = (
        db.query(DeliverableSection)
        .join(Deliverable, DeliverableSection.deliverable_id == Deliverable.id)
        .filter(Deliverable.project_id == project.id)
        .order_by(DeliverableSection.section_key.asc())
        .all()
    )
    return AssistantToolResult(
        tool_name="list_sections",
        result={
            "items": [
                {
                    "id": row.id,
                    "section_key": row.section_key,
                    "title": row.title,
                    "status": row.status,
                }
                for row in rows
            ]
        },
        summary=f"项目「{project.name}」下有 {len(rows)} 个章节。",
    )


def list_pending_reviews(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project_id = arguments.get("project_id")
    query = (
        db.query(ReviewThread, DeliverableSection, Deliverable)
        .join(DeliverableSection, ReviewThread.deliverable_section_id == DeliverableSection.id)
        .join(Deliverable, DeliverableSection.deliverable_id == Deliverable.id)
        .filter(ReviewThread.status == "open")
    )
    if project_id:
        _get_project_for_user(db, user, project_id)
        query = query.filter(Deliverable.project_id == project_id)
    else:
        query = query.join(Project, Deliverable.project_id == Project.id).filter(Project.org_id == (user.org_id or "default"))
    rows = query.limit(20).all()
    return AssistantToolResult(
        tool_name="list_pending_reviews",
        result={
            "items": [
                {
                    "review_thread_id": thread.id,
                    "section_id": section.id,
                    "section_key": section.section_key,
                    "project_id": deliverable.project_id,
                }
                for thread, section, deliverable in rows
            ]
        },
        summary=f"有 {len(rows)} 个待处理评审。",
    )


def open_page(arguments: dict) -> AssistantToolResult:
    route = str(arguments.get("route") or "/")
    allowed_routes = {
        "/",
        "/projects",
        "/pricing",
        "/docs",
        "/settings/providers",
    }
    if route not in allowed_routes and not route.startswith("/projects/"):
        route = "/"
    return AssistantToolResult(
        tool_name="open_page",
        result={"route": route},
        summary="已准备好跳转页面。",
    )


def get_runtime_status(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project_id = arguments.get("project_id")
    if project_id:
        _get_project_for_user(db, user, project_id)
        runs = list_runs_query(db, project_id)
    else:
        runs = []
    return AssistantToolResult(
        tool_name="get_runtime_status",
        result={"runs": [run.model_dump() for run in runs]},
        summary=f"当前上下文里有 {len(runs)} 条执行记录。",
    )


def start_draft_section(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    response = draft_section_command(
        db,
        DraftSectionRequest(
            project_id=arguments["project_id"],
            section_key=arguments["section_key"],
            provider_config_id=arguments.get("provider_config_id"),
            reasoning_effort=arguments.get("reasoning_effort"),
        ),
        user,
    )
    return AssistantToolResult(
        tool_name="start_draft_section",
        result=response.model_dump(),
        summary=f"已启动章节起草工作流，运行 ID：{response.run_id}。",
        workflow=True,
    )


def start_redraft_section(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    response = redraft_section_command(
        db,
        RedraftSectionRequest(
            project_id=arguments["project_id"],
            section_key=arguments["section_key"],
            review_feedback=arguments.get("review_feedback"),
            provider_config_id=arguments.get("provider_config_id"),
            reasoning_effort=arguments.get("reasoning_effort"),
        ),
        user,
    )
    return AssistantToolResult(
        tool_name="start_redraft_section",
        result=response.model_dump(),
        summary=f"已启动章节重写工作流，运行 ID：{response.run_id}。",
        workflow=True,
    )


def _get_project_for_user(db: Session, user: CurrentUser, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise ValueError("Project not found")
    if project.org_id != (user.org_id or "default"):
        raise ValueError("Project not found")
    return project


# ── New read-only tools ──────────────────────────────────────────────────────


def list_requirements_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project = _get_project_for_user(db, user, arguments["project_id"])
    items = list_requirements_query(db, project.id)
    return AssistantToolResult(
        tool_name="list_requirements",
        result={"items": [item.model_dump() for item in items]},
        summary=f"项目「{project.name}」下有 {len(items)} 条需求。",
    )


def list_evidence_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project = _get_project_for_user(db, user, arguments["project_id"])
    items = list_evidence_query(db, project.id)
    return AssistantToolResult(
        tool_name="list_evidence",
        result={"items": [item.model_dump() for item in items]},
        summary=f"项目「{project.name}」下有 {len(items)} 条证据。",
    )


def list_deliverables_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project = _get_project_for_user(db, user, arguments["project_id"])
    items = list_deliverables_query(db, project.id)
    return AssistantToolResult(
        tool_name="list_deliverables",
        result={"items": [item.model_dump() for item in items]},
        summary=f"项目「{project.name}」下有 {len(items)} 个交付物。",
    )


def list_documents_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project = _get_project_for_user(db, user, arguments["project_id"])
    bundle_id = arguments.get("bundle_id")
    if bundle_id:
        items = list_documents_query(db, bundle_id)
    else:
        items = []
    return AssistantToolResult(
        tool_name="list_documents",
        result={"items": [item.model_dump() for item in items]},
        summary=f"找到 {len(items)} 个文档。",
    )


def get_section_versions_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    _get_project_for_user(db, user, arguments["project_id"])
    section_id = arguments.get("section_id", "")
    items = list_versions_query(db, section_id) if section_id else []
    return AssistantToolResult(
        tool_name="get_section_versions",
        result={"items": [item.model_dump() for item in items]},
        summary=f"找到 {len(items)} 个版本。",
    )


# ── New mutation tools ───────────────────────────────────────────────────────


def create_deliverable_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project = _get_project_for_user(db, user, arguments["project_id"])
    title = str(arguments.get("title") or "").strip()
    if not title:
        raise ValueError("Deliverable title is required")
    deliverable = create_deliverable_command(
        db, DeliverableCreate(project_id=project.id, type=arguments.get("type", "proposal"), title=title)
    )
    return AssistantToolResult(
        tool_name="create_deliverable",
        result=deliverable.model_dump(),
        summary=f"交付物「{deliverable.title}」已创建。",
    )


def retry_run_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    run_id = arguments.get("run_id", "")
    if not run_id:
        raise ValueError("run_id is required")
    run = retry_failed_run_command(db, run_id)
    return AssistantToolResult(
        tool_name="retry_run",
        result=run.model_dump(),
        summary=f"已重试运行 {run_id[:8]}。",
    )


def export_deliverable_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    deliverable_id = arguments.get("deliverable_id", "")
    fmt = arguments.get("format", "docx")
    if not deliverable_id:
        raise ValueError("deliverable_id is required")
    deliverable = db.get(Deliverable, deliverable_id)
    if deliverable is None:
        raise ValueError("Deliverable not found")
    if deliverable.status != "approved":
        raise ValueError("Deliverable must be approved before export")
    return AssistantToolResult(
        tool_name="export_deliverable",
        result={"deliverable_id": deliverable_id, "format": fmt, "status": "ready"},
        summary=f"交付物「{deliverable.title}」的 {fmt.upper()} 导出已就绪，请前往导出页面下载。",
    )


def delete_project_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project = _get_project_for_user(db, user, arguments["project_id"])
    name = project.name
    db.delete(project)
    db.commit()
    return AssistantToolResult(
        tool_name="delete_project",
        result={"deleted": True, "project_id": arguments["project_id"]},
        summary=f"项目「{name}」已删除。",
    )


def upload_document_stub(arguments: dict) -> AssistantToolResult:
    return AssistantToolResult(
        tool_name="upload_document",
        result={"action": "redirect_to_ui"},
        summary="文档上传需要通过界面操作。请在项目的资料包页面中点击上传按钮。",
    )
