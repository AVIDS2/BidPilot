"""LangGraph @tool wrappers for the assistant agent.

Each tool closes over db and user, injected via create_tools().
The tool docstrings are critical — the LLM uses them to decide which tool to call.
"""

from __future__ import annotations

import json

from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.access.service import (
    list_accessible_projects,
    require_bundle_capability,
    require_deliverable_capability,
    require_deliverable_section_capability,
    require_execution_run_capability,
    require_project_capability,
)
from app.auth.schemas import CurrentUser
from app.auth.service import check_plan_limit
from app.assistant.attachments import attach_staged_attachments_to_project
from app.bundles.service import list_bundles_query
from app.deliverables.schemas import DeliverableCreate
from app.deliverables.service import create_deliverable_command, list_deliverables_query
from app.documents.service import list_documents_query
from app.drafting.schemas import DraftSectionRequest, RedraftSectionRequest
from app.drafting.service import draft_section_command, redraft_section_command
from app.evidence.service import list_evidence_query
from app.execution.service import list_runs_query, retry_failed_run_command
from app.export.service import generate_deliverable_export_command
from app.memory.schemas import MemoryCreate, MemoryGraphExtractionCreate
from app.memory.service import (
    create_memory_command,
    delete_memory_command,
    list_memory_portfolio_query,
    memory_context_for_agent,
    start_memory_graph_extraction_command,
)
from app.models import Deliverable, DeliverableSection, Project, ReviewThread
from app.projects.demo import create_demo_project_command
from app.projects.schemas import ProjectCreate
from app.projects.service import create_project_command
from app.readiness.service import generate_readiness_pack_command, get_readiness_summary_query, select_readiness_gaps
from app.review.schemas import ReviewDecisionCreate
from app.review.decision_service import canonical_review_decision
from app.review.service import submit_review_decision_command
from app.requirements.service import (
    get_claim_review_queue_query,
    get_requirement_query,
    list_requirements_query,
)
from app.versions.service import list_versions_query
from contracts import MemoryKind, MemoryScope

from .policy import ApprovalMode, get_tool_policy, tool_requires_approval
from .llm import ReasoningEffort


def _normalize_reasoning_effort(value: str | None) -> ReasoningEffort | None:
    if value == "low":
        return "low"
    if value == "medium":
        return "medium"
    if value == "high":
        return "high"
    if value == "extra":
        return "extra"
    if value == "max":
        return "max"
    # Legacy clients called the highest setting "ultra". Preserve intent
    # without carrying a sixth value into the current assistant contract.
    if value == "ultra":
        return "max"
    return None


def _get_project_for_user(db: Session, user: CurrentUser, project_id: str) -> Project:
    return require_project_capability(
        db,
        current_user=user,
        project_id=project_id,
        capability="project.read",
    ).project


def create_tools(
    db: Session,
    user: CurrentUser,
    provider_config_id: str | None = None,
    reasoning_effort: str | None = None,
    approval_mode: ApprovalMode = "risky_only",
) -> list:
    """Create tool list with injected db session and user context."""
    normalized_reasoning_effort = _normalize_reasoning_effort(reasoning_effort)

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
        projects = list_accessible_projects(db, current_user=user)
        if query.strip():
            normalized_query = query.strip().casefold()
            projects = [project for project in projects if normalized_query in project.name.casefold()]
        projects = projects[:10]
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
        check_plan_limit(
            db,
            user.id,
            "projects",
            delta=1,
            org_id=user.org_id,
        )
        project = create_project_command(
            db, ProjectCreate(name=arguments["name"], scenario_package=scenario_package),
            user.org_id or "default",
            user.id,
        )
        return json.dumps(
            {"id": project.id, "name": project.name, "status": "created"},
            ensure_ascii=False,
        )

    @tool
    def create_demo_workspace() -> str:
        """创建或打开一个内置的 BidPilot 演示工作区。不会调用模型或消耗 AI 额度，但会占用一个项目名额，执行前请向用户确认。"""
        arguments: dict = {}
        gated = _approval_gate(
            "create_demo_workspace",
            arguments,
            "需要你确认：我将创建内置演示工作区。它会占用一个项目名额，但不会使用 AI 额度。",
        )
        if gated:
            return gated
        project, created = create_demo_project_command(db, user)
        return json.dumps(
            {"id": project.id, "name": project.name, "status": project.status, "created": created},
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
        bundles = list_bundles_query(db, project.id, current_user=user)
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
            project_ids = [project.id for project in list_accessible_projects(db, current_user=user)]
            if not project_ids:
                return json.dumps({"reviews": [], "count": 0}, ensure_ascii=False)
            query = query.filter(Deliverable.project_id.in_(project_ids))
        rows = query.limit(20).all()
        items = [
            {
                "thread_id": t.id,
                "section_id": s.id,
                "section_version_id": t.section_version_id,
                "section_key": s.section_key,
                "project_id": d.project_id,
            }
            for t, s, d in rows
        ]
        return json.dumps({"reviews": items, "count": len(items)}, ensure_ascii=False)

    @tool
    def submit_review_decision(
        project_id: str,
        section_id: str,
        section_version_id: str,
        decision: str,
        comment: str = "",
    ) -> str:
        """提交章节审核决定。decision 只能是 approved 或 rejected；这会改变审核状态，执行前请向用户确认。"""
        normalized_decision = decision.strip().lower()
        if normalized_decision not in {"approved", "rejected"}:
            return json.dumps({"error": "decision 必须是 approved 或 rejected"}, ensure_ascii=False)
        normalized_decision = canonical_review_decision(normalized_decision)
        section = require_deliverable_section_capability(
            db,
            current_user=user,
            section_id=section_id,
            capability="review.write",
        )
        deliverable = db.get(Deliverable, section.deliverable_id)
        if deliverable is None or deliverable.project_id != project_id:
            return json.dumps({"error": "章节不属于当前项目"}, ensure_ascii=False)
        arguments = {
            "project_id": project_id,
            "section_id": section_id,
            "section_version_id": section_version_id,
            "decision": normalized_decision,
            "comment": comment.strip(),
        }
        gated = _approval_gate(
            "submit_review_decision",
            arguments,
            "需要你确认：我将提交这项章节审核决定。",
        )
        if gated:
            return gated
        review = submit_review_decision_command(
            db,
            ReviewDecisionCreate(
                section_id=section_id,
                section_version_id=section_version_id,
                decision=normalized_decision,
                comment=comment.strip() or None,
            ),
            user,
        )
        return json.dumps(
            {
                "section_id": review.section_id,
                "section_version_id": review.section_version_id,
                "decision": review.decision,
                "review_thread_id": review.id,
            },
            ensure_ascii=False,
        )

    @tool
    def list_requirements(project_id: str) -> str:
        """列出项目下的所有需求（requirements），包含章节键、优先级和状态。"""
        project = _get_project_for_user(db, user, project_id)
        items = list_requirements_query(db, project.id, current_user=user)
        result = [
            {"id": r.id, "section_key": r.section_key, "text": r.requirement_text,
             "priority": r.priority, "status": r.status}
            for r in items
        ]
        return json.dumps({"requirements": result, "count": len(result)}, ensure_ascii=False)

    @tool
    def list_claim_review_queue(project_id: str) -> str:
        """查看当前项目由 AI 生成、仍等待人工核验的主张队列。只返回核验进度计数，不返回草稿主张正文。"""
        project = _get_project_for_user(db, user, project_id)
        queue = get_claim_review_queue_query(db, project.id, current_user=user)
        return json.dumps(
            {
                "project_id": queue.project_id,
                "count": queue.count,
                "ready_to_verify_count": queue.ready_to_verify_count,
                "blocked_by_evidence_count": queue.blocked_by_evidence_count,
                "truncated": queue.truncated,
            },
            ensure_ascii=False,
        )

    @tool
    def get_readiness_summary(project_id: str) -> str:
        """读取投标项目的就绪度、强制项缺口、证据缺口和待处理风险。"""
        _get_project_for_user(db, user, project_id)
        summary = get_readiness_summary_query(db, project_id, current_user=user)
        return json.dumps(
            {
                "project_id": summary.project_id,
                "project_name": summary.project_name,
                "readiness_score": summary.readiness_score,
                "counts": summary.counts.model_dump(),
                "scores": summary.scores.model_dump(),
                "blockers": {
                    "mandatory": len(summary.mandatory_gaps),
                    "evidence": len(summary.evidence_gaps),
                    "contradictions": len(summary.contradictions),
                    "overdue": len(summary.overdue),
                },
            },
            ensure_ascii=False,
        )

    @tool
    def generate_readiness_pack(project_id: str) -> str:
        """生成当前项目的投标准备度 DOCX 和 XLSX 包。会写入交付物存储，执行前请向用户确认。"""
        arguments = {"project_id": project_id}
        gated = _approval_gate(
            "generate_readiness_pack",
            arguments,
            "需要你确认：我将生成当前项目的投标准备度包。",
        )
        if gated:
            return gated
        pack = generate_readiness_pack_command(
            db,
            project_id,
            current_user=user,
            actor_id=user.id,
        )
        return json.dumps(
            {
                "pack_id": pack.id,
                "version_number": pack.version_number,
                "status": pack.status,
                "xlsx_download_path": f"/readiness/packs/{pack.id}/xlsx",
                "docx_download_path": f"/readiness/packs/{pack.id}/docx",
            },
            ensure_ascii=False,
        )

    @tool
    def list_readiness_gaps(project_id: str, kind: str = "all") -> str:
        """列出投标项目的就绪缺口。kind 可为 all、high_risk、mandatory、evidence、contradictions、overdue 或 uncovered。"""
        _get_project_for_user(db, user, project_id)
        summary = get_readiness_summary_query(db, project_id, current_user=user)
        items = select_readiness_gaps(summary, kind=kind)[:20]
        return json.dumps(
            {
                "kind": kind,
                "items": [_readiness_gap_to_result(item) for item in items],
            },
            ensure_ascii=False,
        )

    @tool
    def open_requirement_source(requirement_id: str) -> str:
        """读取某条需求及其原文、来源文档和定位信息。"""
        requirement = get_requirement_query(db, requirement_id, current_user=user)
        return json.dumps(
            {
                "id": requirement.id,
                "requirement_text": requirement.requirement_text,
                "original_text": requirement.original_text,
                "source_document_name": requirement.source_document_name,
                "source_locator_json": requirement.source_locator_json,
                "verification_status": requirement.verification_status,
                "coverage_status": (
                    requirement.bid_profile.coverage_status
                    if requirement.bid_profile
                    else "uncovered"
                ),
            },
            ensure_ascii=False,
        )

    @tool
    def list_evidence(project_id: str) -> str:
        """列出项目下的所有证据引用（evidence），包含引用文本和置信度。"""
        project = _get_project_for_user(db, user, project_id)
        items = list_evidence_query(db, project.id, user)
        result = [
            {"id": e.id, "quote": e.quote_text, "confidence": e.confidence}
            for e in items
        ]
        return json.dumps({"evidence": result, "count": len(result)}, ensure_ascii=False)

    @tool
    def list_deliverables(project_id: str) -> str:
        """列出项目下的所有交付物（deliverables），包含标题和状态。"""
        project = _get_project_for_user(db, user, project_id)
        items = list_deliverables_query(db, project.id, user)
        result = [
            {"id": d.id, "title": d.title, "type": d.type, "status": d.status}
            for d in items
        ]
        return json.dumps({"deliverables": result, "count": len(result)}, ensure_ascii=False)

    @tool
    def list_documents(project_id: str, bundle_id: str = "") -> str:
        """列出项目或指定资料包下的文档。"""
        project = _get_project_for_user(db, user, project_id)
        if bundle_id:
            bundle = require_bundle_capability(
                db,
                current_user=user,
                bundle_id=bundle_id,
                capability="project.read",
            )
            if bundle.project_id != project.id:
                return json.dumps({"error": "资料包不属于当前项目"}, ensure_ascii=False)
            items = list_documents_query(db, bundle_id, user)
        else:
            items = []
        result = [
            {"id": d.id, "filename": d.original_filename, "status": d.parse_status}
            for d in items
        ]
        return json.dumps({"documents": result, "count": len(result)}, ensure_ascii=False)

    @tool
    def attach_uploaded_documents(
        project_id: str,
        attachment_ids: list[str],
        bundle_label: str = "Agent 上传资料",
    ) -> str:
        """把本轮已上传的暂存附件正式加入指定项目资料包并触发解析。仅使用系统提供的附件 ID；执行前请向用户确认。"""
        arguments = {
            "project_id": project_id,
            "attachment_ids": attachment_ids,
            "bundle_label": bundle_label,
        }
        gated = _approval_gate(
            "attach_uploaded_documents",
            arguments,
            f"需要你确认：我将把 {len(attachment_ids)} 个附件加入项目资料包并开始解析。",
        )
        if gated:
            return gated
        result = attach_staged_attachments_to_project(
            db,
            current_user=user,
            project_id=project_id,
            attachment_ids=attachment_ids,
            bundle_label=bundle_label,
        )
        return json.dumps(result, ensure_ascii=False)

    @tool
    def get_section_versions(project_id: str, section_id: str = "") -> str:
        """获取章节的版本历史。"""
        project = _get_project_for_user(db, user, project_id)
        if not section_id:
            return json.dumps({"versions": [], "count": 0}, ensure_ascii=False)
        section = require_deliverable_section_capability(
            db,
            current_user=user,
            section_id=section_id,
            capability="project.read",
        )
        deliverable = db.get(Deliverable, section.deliverable_id)
        if deliverable is None or deliverable.project_id != project.id:
            return json.dumps({"error": "章节不属于当前项目"}, ensure_ascii=False)
        items = list_versions_query(db, section_id, user)
        result = [
            {"id": v.id, "version": v.version_number, "actor": v.created_by_actor}
            for v in items
        ]
        return json.dumps({"versions": result, "count": len(result)}, ensure_ascii=False)

    @tool
    def create_deliverable(project_id: str, title: str, type: str = "proposal") -> str:
        """在项目下创建一个新的交付物。创建前请向用户确认。"""
        project = require_project_capability(
            db,
            current_user=user,
            project_id=project_id,
            capability="project.manage",
        ).project
        arguments = {"project_id": project.id, "title": title.strip(), "type": type}
        gated = _approval_gate("create_deliverable", arguments, f"需要你确认：我将在项目「{project.name}」下创建交付物「{title.strip()}」。")
        if gated:
            return gated
        deliverable = create_deliverable_command(
            db,
            DeliverableCreate(project_id=project.id, type=type, title=title.strip()),
            user,
        )
        return json.dumps(
            {"id": deliverable.id, "title": deliverable.title, "status": "created"},
            ensure_ascii=False,
        )

    @tool
    def start_draft_section(project_id: str, section_key: str) -> str:
        """启动某个章节的 AI 起草工作流。需要项目 ID 和章节键（如 technical-approach、executive-summary）。启动前请向用户确认。"""
        require_project_capability(
            db,
            current_user=user,
            project_id=project_id,
            capability="workflow.run",
        )
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
                reasoning_effort=normalized_reasoning_effort,
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
        require_project_capability(
            db,
            current_user=user,
            project_id=project_id,
            capability="workflow.run",
        )
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
                reasoning_effort=normalized_reasoning_effort,
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
            runs = list_runs_query(db, project_id, user)
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
        require_execution_run_capability(
            db,
            current_user=user,
            run_id=run_id,
            capability="workflow.run",
        )
        gated = _approval_gate("retry_run", {"run_id": run_id}, f"需要你确认：我将重试运行 {run_id[:8]}。")
        if gated:
            return gated
        run = retry_failed_run_command(db, run_id, user)
        return json.dumps(
            {"id": run.id, "type": run.run_type, "status": run.status},
            ensure_ascii=False,
        )

    @tool
    def export_deliverable(project_id: str, deliverable_id: str, format: str = "docx") -> str:
        """导出交付物为 DOCX 或 PDF。交付物必须已审批通过。"""
        deliverable = require_deliverable_capability(
            db,
            current_user=user,
            deliverable_id=deliverable_id,
            capability="deliverables.export",
        )
        if deliverable.project_id != project_id:
            return json.dumps({"error": "交付物不属于当前项目"}, ensure_ascii=False)
        arguments = {"project_id": project_id, "deliverable_id": deliverable_id, "format": format}
        gated = _approval_gate("export_deliverable", arguments, f"需要你确认：我将导出交付物为 {format.upper()}。")
        if gated:
            return gated
        if deliverable.status != "approved":
            return json.dumps(
                {"error": f"交付物状态为 {deliverable.status}，需要先审批通过才能导出"},
                ensure_ascii=False,
            )
        artifact = generate_deliverable_export_command(
            db,
            deliverable_id=deliverable_id,
            artifact_format=format.lower(),
            current_user=user,
            require_approved=True,
        )
        return json.dumps(
            {
                "deliverable_id": deliverable_id,
                "format": format.lower(),
                "status": "ready",
                "download_path": artifact.download_path,
                "persisted": artifact.storage_key is not None,
            },
            ensure_ascii=False,
        )

    @tool
    def delete_project(project_id: str, confirmation_text: str = "") -> str:
        """删除指定项目。危险操作：必须先向用户展示项目名称，并要求用户输入完整项目名称作为 confirmation_text。"""
        project = require_project_capability(
            db,
            current_user=user,
            project_id=project_id,
            capability="project.delete",
        ).project
        return _confirmation_response(
            "delete_project",
            {"project_id": project.id},
            f"需要你确认：删除项目「{project.name}」后，项目资料、章节和交付物将无法恢复。请输入完整项目名称后我再执行删除。",
            expected_text=project.name,
        )

    @tool
    def semantic_search(project_id: str, query: str) -> str:
        """在项目的知识库中进行语义搜索，返回相关文档片段。"""
        from app.retrieval.service import search_knowledge

        response = search_knowledge(
            db,
            project_id=project_id,
            query=query,
            current_user=user,
        )
        items = [
            {
                "chunk_id": result.chunk_id,
                "score": round(result.score, 4),
                "content": result.content[:200],
                "source_document_id": result.source_document_id,
                "citation": result.citation.model_dump(mode="json"),
            }
            for result in response.results
        ]
        return json.dumps(
            {
                "results": items,
                "count": len(items),
                "degraded_reasons": response.degraded_reasons,
            },
            ensure_ascii=False,
        )

    @tool
    def search_bid_wiki(query: str, project_id: str = "") -> str:
        """查询当前用户或项目已审批的 Bid Wiki 记忆，结果始终带来源摘要。"""
        if not query.strip():
            return json.dumps({"error": "查询内容不能为空"}, ensure_ascii=False)
        context = memory_context_for_agent(
            db,
            current_user=user,
            project_id=project_id or None,
            query=query,
        )
        items = [
            {
                "id": item.record_id,
                "title": item.title,
                "body_markdown": item.body_markdown,
                "scope": item.scope.value,
                "kind": item.kind.value,
                "citations": [citation.model_dump(exclude_none=True) for citation in item.citations],
            }
            for item in context.items
        ]
        return json.dumps(
            {
                "items": items,
                "count": len(items),
                "memory_version": context.memory_version,
                "degraded_reasons": context.degraded_reasons,
            },
            ensure_ascii=False,
        )

    @tool
    def list_knowledge_portfolio() -> str:
        """查看可访问项目的知识资产健康度。

        只返回项目名称、共享知识数量、可见的待审核数量和编译状态，绝不返回
        记忆正文、证据、用户私有记忆或跨项目检索结果。用它帮助用户选择项目；
        若用户需要知识内容，先让其打开具体项目后再调用 search_bid_wiki。
        """
        items = [item.model_dump(mode="json") for item in list_memory_portfolio_query(db, user, limit=50)]
        return json.dumps({"items": items, "count": len(items)}, ensure_ascii=False)

    @tool
    def propose_memory(body_markdown: str, title: str = "个人工作偏好") -> str:
        """保存用户明确要求记住的个人工作偏好。执行前必须向用户确认。"""
        arguments = {
            "scope": MemoryScope.USER_PRIVATE.value,
            "kind": MemoryKind.PREFERENCE.value,
            "title": title.strip() or "个人工作偏好",
            "body_markdown": body_markdown.strip(),
        }
        if not arguments["body_markdown"]:
            return json.dumps({"error": "需要提供要记住的具体内容"}, ensure_ascii=False)
        gated = _approval_gate("propose_memory", arguments, "需要你确认：我将保存这条个人工作偏好。")
        if gated:
            return gated
        record = create_memory_command(db, MemoryCreate(**arguments), user)
        return json.dumps(
            {"id": record.id, "status": record.status.value, "scope": record.scope.value},
            ensure_ascii=False,
        )

    @tool
    def propose_memory_graph(project_id: str, memory_record_id: str) -> str:
        """从一条已激活、带来源的项目共享知识生成实体关系提案。

        只能使用用户明确提供的 memory_record_id，不能猜测来源。该操作会调用
        模型、消耗额度，且结果只进入待审核队列，不会自动进入 Agent 或检索上下文。
        """
        arguments = {"project_id": project_id, "memory_record_id": memory_record_id}
        gated = _approval_gate(
            "propose_memory_graph",
            arguments,
            "需要你确认：我将从这条已验证的项目知识生成实体关系提案。结果仍需人工审核。",
        )
        if gated:
            return gated
        response = start_memory_graph_extraction_command(
            db,
            MemoryGraphExtractionCreate(
                project_id=project_id,
                memory_record_id=memory_record_id,
                provider_config_id=provider_config_id,
                reasoning_effort=normalized_reasoning_effort,
            ),
            user,
        )
        return json.dumps(
            {
                "run_id": response.run_id,
                "runtime_run_id": response.runtime_run_id,
                "status": response.status,
                "reused": response.reused,
            },
            ensure_ascii=False,
        )

    @tool
    def forget_memory(memory_id: str) -> str:
        """遗忘一条记忆。执行前必须向用户确认，且无法恢复到后续 Agent 上下文。"""
        if not memory_id.strip():
            return json.dumps({"error": "需要提供记忆 ID"}, ensure_ascii=False)
        arguments = {"memory_id": memory_id.strip()}
        gated = _approval_gate("forget_memory", arguments, "需要你确认：我将遗忘这条记忆。")
        if gated:
            return gated
        delete_memory_command(db, arguments["memory_id"], user)
        return json.dumps({"deleted": True, "memory_id": arguments["memory_id"]}, ensure_ascii=False)

    @tool
    def open_page(route: str) -> str:
        """导航到指定的前端页面。可用路由：/projects, /knowledge, /pricing, /docs, /settings/providers, /dashboard"""
        allowed = {"/", "/projects", "/knowledge", "/pricing", "/docs", "/settings/providers", "/dashboard"}
        if route not in allowed and not route.startswith("/projects/"):
            route = "/projects"
        return json.dumps({"route": route, "action": "navigate"}, ensure_ascii=False)

    return [
        search_projects, create_project, create_demo_workspace, get_project_summary,
        list_project_bundles, list_sections, list_pending_reviews, submit_review_decision,
        list_requirements, list_claim_review_queue, get_readiness_summary, generate_readiness_pack, list_readiness_gaps, open_requirement_source,
        list_evidence, list_deliverables, list_documents, attach_uploaded_documents,
        get_section_versions, create_deliverable,
        start_draft_section, start_redraft_section,
        get_runtime_status, retry_run, export_deliverable,
        delete_project, semantic_search, search_bid_wiki, list_knowledge_portfolio, propose_memory, propose_memory_graph,
        forget_memory, open_page,
    ]


def _readiness_gap_to_result(item) -> dict:
    return {
        "id": item.id,
        "requirement_text": item.requirement_text,
        "risk_level": item.risk_level,
        "coverage_status": item.coverage_status,
        "evidence_status": item.evidence_status,
        "owner_user_id": item.owner_user_id,
        "source_locator_json": item.source_locator_json,
    }
