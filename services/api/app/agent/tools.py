"""LangGraph @tool wrappers for the assistant agent.

Each tool closes over db and user, injected via create_tools().
The tool docstrings are critical — the LLM uses them to decide which tool to call.
"""

from __future__ import annotations

import json

from langchain_core.tools import tool
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

from .policy import ApprovalMode, get_tool_policy, tool_requires_approval


def _get_project_for_user(db: Session, user: CurrentUser, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise ValueError("Project not found")
    if project.org_id != (user.org_id or "default"):
        raise ValueError("Project not found")
    return project


def create_tools(
    db: Session,
    user: CurrentUser,
    provider_config_id: str | None = None,
    reasoning_effort: str | None = None,
    approval_mode: ApprovalMode = "risky_only",
) -> list:
    """Create tool list with injected db session and user context."""

    def _confirmation_response(
        tool_name: str,
        arguments: dict,
        message: str,
        *,
        expected_text: str | None = None,
    ) -> str:
        policy = get_tool_policy(tool_name)
        payload = {
            "requires_confirmation": True,
            "tool_name": tool_name,
            "arguments": arguments,
            "message": message,
            "requires_typed_confirmation": bool(policy and policy.requires_typed_confirmation),
        }
        if expected_text is not None:
            payload["expected_text"] = expected_text
        return json.dumps(payload, ensure_ascii=False)

    def _approval_gate(tool_name: str, arguments: dict, message: str) -> str | None:
        if not tool_requires_approval(tool_name, approval_mode):
            return None
        return _confirmation_response(tool_name, arguments, message)

    @tool
    def search_projects(query: str = "") -> str:
        """搜索当前用户的项目。返回项目列表（名称、状态、场景包）。"""
        stmt = __import__("sqlalchemy").select(Project).where(
            Project.org_id == (user.org_id or "default")
        )
        if query.strip():
            stmt = stmt.where(Project.name.ilike(f"%{query.strip()}%"))
        projects = db.scalars(stmt.order_by(Project.created_at.desc()).limit(10)).all()
        items = [
            {"id": p.id, "name": p.name, "status": p.status, "scenario": p.scenario_package}
            for p in projects
        ]
        return json.dumps({"projects": items, "count": len(items)}, ensure_ascii=False)

    @tool
    def create_project(name: str, scenario_package: str = "bidpilot") -> str:
        """创建一个新的投标项目。需要项目名称。创建前请向用户确认。"""
        if not name.strip():
            return json.dumps({"error": "项目名称不能为空"}, ensure_ascii=False)
        arguments = {"name": name.strip(), "scenario_package": scenario_package}
        gated = _approval_gate("create_project", arguments, f"需要你确认：我将创建项目「{name.strip()}」。")
        if gated:
            return gated
        check_plan_limit(db, user.id, "projects", delta=1, plan=user.plan)
        project = create_project_command(
            db, ProjectCreate(name=arguments["name"], scenario_package=scenario_package),
            user.org_id or "default",
        )
        return json.dumps(
            {"id": project.id, "name": project.name, "status": "created"},
            ensure_ascii=False,
        )

    @tool
    def get_project_summary(project_id: str) -> str:
        """获取项目的详细摘要信息（名称、状态、场景包）。"""
        project = _get_project_for_user(db, user, project_id)
        return json.dumps(
            {"id": project.id, "name": project.name, "status": project.status,
             "scenario": project.scenario_package},
            ensure_ascii=False,
        )

    @tool
    def list_project_bundles(project_id: str) -> str:
        """列出项目下的所有资料包（bundles），包含标签和解析状态。"""
        project = _get_project_for_user(db, user, project_id)
        bundles = list_bundles_query(db, project.id)
        items = [
            {"id": b.id, "label": b.label, "status": b.ingest_status}
            for b in bundles
        ]
        return json.dumps({"bundles": items, "count": len(items)}, ensure_ascii=False)

    @tool
    def list_sections(project_id: str) -> str:
        """列出项目下所有交付物的章节（sections），包含章节键和状态。"""
        project = _get_project_for_user(db, user, project_id)
        rows = (
            db.query(DeliverableSection)
            .join(Deliverable, DeliverableSection.deliverable_id == Deliverable.id)
            .filter(Deliverable.project_id == project.id)
            .order_by(DeliverableSection.section_key.asc())
            .all()
        )
        items = [
            {"id": r.id, "section_key": r.section_key, "title": r.title, "status": r.status}
            for r in rows
        ]
        return json.dumps({"sections": items, "count": len(items)}, ensure_ascii=False)

    @tool
    def list_pending_reviews(project_id: str = "") -> str:
        """列出待处理的审核线程。可按项目过滤。"""
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
            query = query.join(Project, Deliverable.project_id == Project.id).filter(
                Project.org_id == (user.org_id or "default")
            )
        rows = query.limit(20).all()
        items = [
            {"thread_id": t.id, "section_key": s.section_key, "project_id": d.project_id}
            for t, s, d in rows
        ]
        return json.dumps({"reviews": items, "count": len(items)}, ensure_ascii=False)

    @tool
    def list_requirements(project_id: str) -> str:
        """列出项目下的所有需求（requirements），包含章节键、优先级和状态。"""
        project = _get_project_for_user(db, user, project_id)
        items = list_requirements_query(db, project.id)
        result = [
            {"id": r.id, "section_key": r.section_key, "text": r.requirement_text,
             "priority": r.priority, "status": r.status}
            for r in items
        ]
        return json.dumps({"requirements": result, "count": len(result)}, ensure_ascii=False)

    @tool
    def list_evidence(project_id: str) -> str:
        """列出项目下的所有证据引用（evidence），包含引用文本和置信度。"""
        project = _get_project_for_user(db, user, project_id)
        items = list_evidence_query(db, project.id)
        result = [
            {"id": e.id, "quote": e.quote_text, "confidence": e.confidence}
            for e in items
        ]
        return json.dumps({"evidence": result, "count": len(result)}, ensure_ascii=False)

    @tool
    def list_deliverables(project_id: str) -> str:
        """列出项目下的所有交付物（deliverables），包含标题和状态。"""
        project = _get_project_for_user(db, user, project_id)
        items = list_deliverables_query(db, project.id)
        result = [
            {"id": d.id, "title": d.title, "type": d.type, "status": d.status}
            for d in items
        ]
        return json.dumps({"deliverables": result, "count": len(result)}, ensure_ascii=False)

    @tool
    def list_documents(project_id: str, bundle_id: str = "") -> str:
        """列出项目或指定资料包下的文档。"""
        if bundle_id:
            items = list_documents_query(db, bundle_id)
        else:
            items = []
        result = [
            {"id": d.id, "filename": d.original_filename, "status": d.parse_status}
            for d in items
        ]
        return json.dumps({"documents": result, "count": len(result)}, ensure_ascii=False)

    @tool
    def get_section_versions(project_id: str, section_id: str = "") -> str:
        """获取章节的版本历史。"""
        if not section_id:
            return json.dumps({"versions": [], "count": 0}, ensure_ascii=False)
        items = list_versions_query(db, section_id)
        result = [
            {"id": v.id, "version": v.version_number, "actor": v.created_by_actor}
            for v in items
        ]
        return json.dumps({"versions": result, "count": len(result)}, ensure_ascii=False)

    @tool
    def create_deliverable(project_id: str, title: str, type: str = "proposal") -> str:
        """在项目下创建一个新的交付物。创建前请向用户确认。"""
        project = _get_project_for_user(db, user, project_id)
        arguments = {"project_id": project.id, "title": title.strip(), "type": type}
        gated = _approval_gate("create_deliverable", arguments, f"需要你确认：我将在项目「{project.name}」下创建交付物「{title.strip()}」。")
        if gated:
            return gated
        deliverable = create_deliverable_command(
            db, DeliverableCreate(project_id=project.id, type=type, title=title.strip())
        )
        return json.dumps(
            {"id": deliverable.id, "title": deliverable.title, "status": "created"},
            ensure_ascii=False,
        )

    @tool
    def start_draft_section(project_id: str, section_key: str) -> str:
        """启动某个章节的 AI 起草工作流。需要项目 ID 和章节键（如 technical-approach、executive-summary）。启动前请向用户确认。"""
        _get_project_for_user(db, user, project_id)
        arguments = {"project_id": project_id, "section_key": section_key}
        gated = _approval_gate("start_draft_section", arguments, f"需要你确认：我将启动章节「{section_key}」的起草工作流。")
        if gated:
            return gated
        response = draft_section_command(
            db,
            DraftSectionRequest(
                project_id=project_id,
                section_key=section_key,
                provider_config_id=provider_config_id,
                reasoning_effort=reasoning_effort,
            ),
            user,
        )
        return json.dumps(
            {"run_id": response.run_id, "status": "started", "section_key": section_key},
            ensure_ascii=False,
        )

    @tool
    def start_redraft_section(project_id: str, section_key: str, review_feedback: str = "") -> str:
        """基于反馈重新起草某个章节。启动前请向用户确认。"""
        _get_project_for_user(db, user, project_id)
        arguments = {"project_id": project_id, "section_key": section_key, "review_feedback": review_feedback}
        gated = _approval_gate("start_redraft_section", arguments, f"需要你确认：我将启动章节「{section_key}」的重写工作流。")
        if gated:
            return gated
        response = redraft_section_command(
            db,
            RedraftSectionRequest(
                project_id=project_id,
                section_key=section_key,
                review_feedback=review_feedback or None,
                provider_config_id=provider_config_id,
                reasoning_effort=reasoning_effort,
            ),
            user,
        )
        return json.dumps(
            {"run_id": response.run_id, "status": "started", "section_key": section_key},
            ensure_ascii=False,
        )

    @tool
    def get_runtime_status(project_id: str = "") -> str:
        """获取项目的执行运行状态列表。"""
        if project_id:
            _get_project_for_user(db, user, project_id)
            runs = list_runs_query(db, project_id)
        else:
            runs = []
        result = [
            {"id": r.id, "type": r.run_type, "status": r.status}
            for r in runs
        ]
        return json.dumps({"runs": result, "count": len(result)}, ensure_ascii=False)

    @tool
    def retry_run(run_id: str) -> str:
        """重试一个失败的执行运行。重试前请向用户确认。"""
        gated = _approval_gate("retry_run", {"run_id": run_id}, f"需要你确认：我将重试运行 {run_id[:8]}。")
        if gated:
            return gated
        run = retry_failed_run_command(db, run_id)
        return json.dumps(
            {"id": run.id, "type": run.run_type, "status": run.status},
            ensure_ascii=False,
        )

    @tool
    def export_deliverable(project_id: str, deliverable_id: str, format: str = "docx") -> str:
        """导出交付物为 DOCX 或 PDF。交付物必须已审批通过。"""
        arguments = {"project_id": project_id, "deliverable_id": deliverable_id, "format": format}
        gated = _approval_gate("export_deliverable", arguments, f"需要你确认：我将导出交付物为 {format.upper()}。")
        if gated:
            return gated
        deliverable = db.get(Deliverable, deliverable_id)
        if deliverable is None:
            return json.dumps({"error": "交付物不存在"}, ensure_ascii=False)
        if deliverable.status != "approved":
            return json.dumps(
                {"error": f"交付物状态为 {deliverable.status}，需要先审批通过才能导出"},
                ensure_ascii=False,
            )
        return json.dumps(
            {"deliverable_id": deliverable_id, "format": format, "status": "ready",
             "message": f"请前往项目详情页的导出标签页下载 {format.upper()} 文件"},
            ensure_ascii=False,
        )

    @tool
    def delete_project(project_id: str, confirmation_text: str = "") -> str:
        """删除指定项目。危险操作：必须先向用户展示项目名称，并要求用户输入完整项目名称作为 confirmation_text。"""
        project = _get_project_for_user(db, user, project_id)
        return _confirmation_response(
            "delete_project",
            {"project_id": project.id},
            f"需要你确认：删除项目「{project.name}」后，项目资料、章节和交付物将无法恢复。请输入完整项目名称后我再执行删除。",
            expected_text=project.name,
        )

    @tool
    def semantic_search(project_id: str, query: str) -> str:
        """在项目的知识库中进行语义搜索，返回相关文档片段。"""
        _get_project_for_user(db, user, project_id)
        from app.retrieval.service import search_knowledge
        results = search_knowledge(db, project_id, query)
        items = [
            {"chunk_id": r.chunk_id, "score": round(r.score, 4), "content": r.content[:200]}
            for r in results
        ]
        return json.dumps({"results": items, "count": len(items)}, ensure_ascii=False)

    @tool
    def open_page(route: str) -> str:
        """导航到指定的前端页面。可用路由：/projects, /pricing, /docs, /settings/providers, /dashboard"""
        allowed = {"/", "/projects", "/pricing", "/docs", "/settings/providers", "/dashboard"}
        if route not in allowed and not route.startswith("/projects/"):
            route = "/projects"
        return json.dumps({"route": route, "action": "navigate"}, ensure_ascii=False)

    return [
        search_projects, create_project, get_project_summary,
        list_project_bundles, list_sections, list_pending_reviews,
        list_requirements, list_evidence, list_deliverables, list_documents,
        get_section_versions, create_deliverable,
        start_draft_section, start_redraft_section,
        get_runtime_status, retry_run, export_deliverable,
        delete_project, semantic_search, open_page,
    ]
