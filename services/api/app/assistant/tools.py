"""Typed platform tools exposed to the assistant harness."""

from __future__ import annotations

from typing import Any, Literal, cast

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
from app.drafting.schemas import DraftSectionRequest, RedraftSectionRequest, ResumeRunRequest
from app.drafting.service import draft_section_command, redraft_section_command, resume_run_command
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
from app.models import Deliverable, DeliverableSection, Project, ReviewThread, SectionVersion
from app.projects.schemas import ProjectCreate
from app.projects.demo import create_demo_project_command
from app.projects.service import create_project_command, delete_project_command_for_user
from app.readiness.service import (
    READINESS_GAP_KINDS,
    generate_readiness_pack_command,
    get_readiness_summary_query,
    select_readiness_gaps,
)
from app.review.schemas import ReviewDecisionCreate
from app.review.decision_service import canonical_review_decision
from app.review.service import submit_review_decision_command
from app.runtime.failures import classify_capability_failure
from app.requirements.service import (
    get_claim_review_queue_query,
    get_requirement_query,
    list_requirements_query,
)
from app.versions.service import list_versions_query
from contracts import MemoryKind, MemoryScope

from .schemas import AssistantToolResult


def execute_tool(
    db: Session,
    user: CurrentUser,
    tool_name: str,
    arguments: dict,
) -> AssistantToolResult:
    if tool_name == "search_projects":
        return search_projects(db, user, arguments)
    if tool_name == "create_demo_workspace":
        return create_demo_workspace(db, user, arguments)
    if tool_name == "create_project":
        return create_project(db, user, arguments)
    if tool_name == "get_project_summary":
        return get_project_summary(db, user, arguments)
    if tool_name == "list_project_bundles":
        return list_project_bundles(db, user, arguments)
    if tool_name == "list_sections":
        return list_sections(db, user, arguments)
    if tool_name == "get_project_outline":
        return get_project_outline(db, user, arguments)
    if tool_name == "search_bid_wiki":
        return search_bid_wiki_tool(db, user, arguments)
    if tool_name == "list_knowledge_portfolio":
        return list_knowledge_portfolio_tool(db, user)
    if tool_name == "propose_memory":
        return propose_memory_tool(db, user, arguments)
    if tool_name == "propose_memory_graph":
        return propose_memory_graph_tool(db, user, arguments)
    if tool_name == "forget_memory":
        return forget_memory_tool(db, user, arguments)
    if tool_name == "list_pending_reviews":
        return list_pending_reviews(db, user, arguments)
    if tool_name == "submit_review_decision":
        return submit_review_decision_tool(db, user, arguments)
    if tool_name == "open_page":
        return open_page(arguments)
    if tool_name == "get_runtime_status":
        return get_runtime_status(db, user, arguments)
    if tool_name == "start_draft_section":
        return start_draft_section(db, user, arguments)
    if tool_name == "write_section":
        return write_section_tool(db, user, arguments)
    if tool_name == "run_section_campaign":
        return run_section_campaign_tool(db, user, arguments)
    if tool_name == "start_redraft_section":
        return start_redraft_section(db, user, arguments)
    if tool_name == "resume_draft_run":
        return resume_draft_run_tool(db, user, arguments)
    if tool_name == "list_requirements":
        return list_requirements_tool(db, user, arguments)
    if tool_name == "list_claim_review_queue":
        return list_claim_review_queue_tool(db, user, arguments)
    if tool_name == "get_readiness_summary":
        return get_readiness_summary_tool(db, user, arguments)
    if tool_name == "list_readiness_gaps":
        return list_readiness_gaps_tool(db, user, arguments)
    if tool_name == "open_requirement_source":
        return open_requirement_source_tool(db, user, arguments)
    if tool_name == "list_evidence":
        return list_evidence_tool(db, user, arguments)
    if tool_name == "list_deliverables":
        return list_deliverables_tool(db, user, arguments)
    if tool_name == "list_documents":
        return list_documents_tool(db, user, arguments)
    if tool_name == "attach_uploaded_documents":
        return attach_uploaded_documents_tool(db, user, arguments)
    if tool_name == "get_section_versions":
        return get_section_versions_tool(db, user, arguments)
    if tool_name == "create_deliverable":
        return create_deliverable_tool(db, user, arguments)
    if tool_name == "retry_run":
        return retry_run_tool(db, user, arguments)
    if tool_name == "export_deliverable":
        return export_deliverable_tool(db, user, arguments)
    if tool_name == "generate_readiness_pack":
        return generate_readiness_pack_tool(db, user, arguments)
    if tool_name == "delete_project":
        return delete_project_tool(db, user, arguments)
    if tool_name == "semantic_search":
        return semantic_search_tool(db, user, arguments)
    if tool_name == "start_deep_research":
        return start_deep_research_tool(db, user, arguments)
    if tool_name == "web_search":
        return web_search_tool(db, user, arguments)
    if tool_name == "discover_remote_documents":
        return discover_remote_documents_tool(db, user, arguments)
    if tool_name == "fetch_url_to_project":
        return fetch_url_to_project_tool(db, user, arguments)
    if tool_name == "upload_document":
        return upload_document_tool(db, user, arguments)
    raise ValueError(f"Unsupported assistant tool: {tool_name}")


def search_projects(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    query = (arguments.get("query") or "").strip()
    projects = list_accessible_projects(db, current_user=user)
    if query:
        normalized_query = query.casefold()
        projects = [project for project in projects if normalized_query in project.name.casefold()]
    projects = projects[:10]
    items = [
        {
            "id": project.id,
            "short_id": project.id[:8],
            "name": project.name,
            "status": project.status,
            "scenario_package": project.scenario_package,
            "created_at": project.created_at.isoformat() if project.created_at else None,
        }
        for project in projects
    ]
    # Surface collisions so the model cannot invent "(1)/(2)" labels without ids.
    name_counts: dict[str, int] = {}
    for item in items:
        name_counts[item["name"]] = name_counts.get(item["name"], 0) + 1
    for item in items:
        item["name_collision"] = name_counts.get(item["name"], 0) > 1
    if not items:
        summary = "没有找到匹配的项目。"
    elif any(item["name_collision"] for item in items):
        lines = [
            f"- {item['name']} · id={item['short_id']} · {item['status']}"
            + (f" · 创建于 {item['created_at'][:10]}" if item.get("created_at") else "")
            for item in items
        ]
        summary = "找到 {count} 个项目（存在同名，请用 short_id/id 区分）：\n{lines}".format(
            count=len(items),
            lines="\n".join(lines),
        )
    else:
        summary = f"找到 {len(items)} 个项目。"
    return AssistantToolResult(
        tool_name="search_projects",
        result={"items": items, "count": len(items)},
        summary=summary,
    )


def create_project(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    name = str(arguments.get("name") or "").strip()
    if not name:
        raise ValueError("Project name is required")

    check_plan_limit(
        db,
        user.id,
        "projects",
        delta=1,
        org_id=user.org_id,
    )
    project = create_project_command(
        db,
        ProjectCreate(
            name=name,
            scenario_package=arguments.get("scenario_package") or "bidpilot",
        ),
        user.org_id or "default",
        user.id,
    )
    return AssistantToolResult(
        tool_name="create_project",
        result=project.model_dump(),
        summary=f"项目「{project.name}」已创建。",
    )


def create_demo_workspace(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project, created = create_demo_project_command(db, user)
    result = {**project.model_dump(), "created": created}
    summary = (
        f"演示工作区「{project.name}」已准备好。"
        if created
        else f"已打开现有演示工作区「{project.name}」。"
    )
    return AssistantToolResult(
        tool_name="create_demo_workspace",
        result=result,
        summary=summary,
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
    bundles = list_bundles_query(db, project.id, current_user=user)
    return AssistantToolResult(
        tool_name="list_project_bundles",
        result={"items": [bundle.model_dump() for bundle in bundles]},
        summary=f"项目「{project.name}」下有 {len(bundles)} 个资料包。",
    )


def list_sections(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project = _get_project_for_user(db, user, arguments["project_id"])
    rows = (
        db.query(DeliverableSection, Deliverable)
        .join(Deliverable, DeliverableSection.deliverable_id == Deliverable.id)
        .filter(Deliverable.project_id == project.id)
        .order_by(Deliverable.title.asc(), DeliverableSection.sort_order.asc(), DeliverableSection.id.asc())
        .all()
    )
    from sqlalchemy import func, select

    from app.models import SectionVersion

    items: list[dict] = []
    for row, deliverable in rows:
        version_count = db.scalar(
            select(func.count())
            .select_from(SectionVersion)
            .where(SectionVersion.deliverable_section_id == row.id)
        ) or 0
        latest = db.scalar(
            select(SectionVersion)
            .where(SectionVersion.deliverable_section_id == row.id)
            .order_by(SectionVersion.version_number.desc())
            .limit(1)
        )
        items.append(
            {
                "id": row.id,
                "deliverable_id": row.deliverable_id,
                "deliverable_title": deliverable.title,
                "section_key": row.section_key,
                "title": row.title,
                "status": row.status,
                "version_count": int(version_count),
                "has_content": bool(version_count),
                "latest_version_id": latest.id if latest else None,
                "latest_version_number": latest.version_number if latest else None,
            }
        )
    drafted = sum(1 for item in items if item["has_content"])
    approved = sum(1 for item in items if item["status"] == "approved")
    return AssistantToolResult(
        tool_name="list_sections",
        result={
            "items": items,
            "outline_count": len(items),
            "drafted_count": drafted,
            "approved_count": approved,
        },
        summary=(
            f"项目「{project.name}」大纲共 {len(items)} 章，"
            f"已起草 {drafted} 章，已批准 {approved} 章。"
        ),
    )


def get_project_outline(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    """Outline-first view: scenario sections + drafting/approval progress."""
    import os

    project_id = str(arguments.get("project_id") or "").strip()
    recovered_from: str | None = None
    try:
        project = _get_project_for_user(db, user, project_id)
    except Exception:
        # Policy switch: when a bad id fails and the user has exactly one accessible
        # project, auto-retry once. Disable with DOCPILOT_OUTLINE_AUTO_RECOVERY=false.
        enabled = os.getenv("DOCPILOT_OUTLINE_AUTO_RECOVERY", "true").lower() not in {
            "0",
            "false",
            "no",
            "off",
        }
        if not enabled:
            raise
        accessible = list_accessible_projects(db, current_user=user)
        if len(accessible) != 1:
            raise
        project = accessible[0]
        recovered_from = project_id or "invalid"
        project_id = project.id
        arguments = {**arguments, "project_id": project_id}
    result = list_sections(db, user, {"project_id": project_id})
    scenario_key = project.scenario_package or "bidpilot"
    try:
        from app.scenarios.templates import get_sections_for_scenario

        template = get_sections_for_scenario(scenario_key)
    except Exception:
        template = []
    existing_by_key: dict[str, list[dict]] = {}
    for item in result.result.get("items", []):
        if not isinstance(item, dict):
            continue
        section_key = str(item.get("section_key") or "").strip()
        if section_key:
            existing_by_key.setdefault(section_key, []).append(item)
    ordered: list[dict] = []
    for sec in template:
        key = sec["section_key"]
        matched = existing_by_key.pop(key, [])
        if matched:
            ordered.extend({**item, "in_template": True} for item in matched)
        else:
            ordered.append(
                {
                    "id": None,
                    "deliverable_id": None,
                    "section_key": key,
                    "title": sec["title"],
                    "status": "missing",
                    "version_count": 0,
                    "has_content": False,
                    "latest_version_id": None,
                    "latest_version_number": None,
                    "in_template": True,
                }
            )
    # Append any extra sections not in the scenario template.
    for items in existing_by_key.values():
        ordered.extend({**item, "in_template": False} for item in items)

    drafted = sum(1 for item in ordered if item["has_content"])
    approved = sum(1 for item in ordered if item["status"] == "approved")
    payload = {
        "project_id": project.id,
        "project_name": project.name,
        "scenario_package": scenario_key,
        "items": ordered,
        "outline_count": len(ordered),
        "drafted_count": drafted,
        "approved_count": approved,
    }
    summary = (
        f"项目「{project.name}」大纲（{scenario_key}）共 {len(ordered)} 章，"
        f"已起草 {drafted} 章，已批准 {approved} 章。"
    )
    if recovered_from is not None:
        payload["recovered_from_project_id"] = recovered_from
        payload["auto_recovered"] = True
        summary = (
            f"原 project_id 无效，已自动切换到唯一可访问项目「{project.name}」"
            f"（{project.id[:8]}）。"
        ) + summary
    return AssistantToolResult(
        tool_name="get_project_outline",
        result=payload,
        summary=summary,
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
        project_ids = [project.id for project in list_accessible_projects(db, current_user=user)]
        if not project_ids:
            return AssistantToolResult(
                tool_name="list_pending_reviews",
                result={"items": []},
                summary="有 0 个待处理评审。",
            )
        query = query.filter(Deliverable.project_id.in_(project_ids))
    rows = query.limit(20).all()
    return AssistantToolResult(
        tool_name="list_pending_reviews",
        result={
            "items": [
                {
                    "review_thread_id": thread.id,
                    "section_id": section.id,
                    "section_version_id": thread.section_version_id,
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
        "/knowledge",
        "/pricing",
        "/docs",
        "/settings/providers",
    }
    if route not in allowed_routes and not route.startswith("/projects/") and not route.startswith("/projects?"):
        route = "/"
    result: dict[str, object] = {"route": route}
    if "surface=workflow" in route:
        result["ui_action"] = {
            "type": "canvas",
            "label": "打开任务编排画布",
            "route": route,
        }
    return AssistantToolResult(
        tool_name="open_page",
        result=result,
        summary="已准备好任务编排画布入口，请点击打开。" if "surface=workflow" in route else "已准备好跳转页面。",
    )


def get_runtime_status(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project_id = arguments.get("project_id")
    if project_id:
        _get_project_for_user(db, user, project_id)
        runs = list_runs_query(db, project_id, user)
    else:
        runs = []
    return AssistantToolResult(
        tool_name="get_runtime_status",
        result={"runs": [run.model_dump() for run in runs]},
        summary=f"当前上下文里有 {len(runs)} 条执行记录。",
    )


def _find_or_create_section_for_write(
    db: Session,
    *,
    project: Project,
    section_key: str,
    deliverable_section_id: str | None = None,
    title: str | None = None,
) -> DeliverableSection:
    """Mirror worker outline-first section creation for lightweight writes."""
    from sqlalchemy import func, select

    if deliverable_section_id:
        section = db.get(DeliverableSection, deliverable_section_id)
        deliverable = db.get(Deliverable, section.deliverable_id) if section else None
        if section is None or deliverable is None or deliverable.project_id != project.id:
            raise ValueError("deliverable_section_not_found")
        if section.section_key != section_key:
            raise ValueError("section_target_mismatch")
    else:
        matches = list(
            db.scalars(
                select(DeliverableSection)
                .join(Deliverable, Deliverable.id == DeliverableSection.deliverable_id)
                .where(
                    Deliverable.project_id == project.id,
                    DeliverableSection.section_key == section_key,
                )
                .order_by(DeliverableSection.id.asc())
                .limit(2)
            ).all()
        )
        if len(matches) > 1:
            raise ValueError("section_key_ambiguous: 请指定 section_id")
        section = matches[0] if matches else None
    if section is not None:
        if title and title.strip() and section.title != title.strip():
            section.title = title.strip()
        return section

    deliverable = db.scalar(select(Deliverable).where(Deliverable.project_id == project.id).limit(1))
    if deliverable is None:
        deliverable = Deliverable(
            project_id=project.id,
            type="proposal",
            title=project.name or "提案交付物",
            status="draft",
        )
        db.add(deliverable)
        db.flush()

    next_order = db.scalar(
        select(func.max(DeliverableSection.sort_order)).where(
            DeliverableSection.deliverable_id == deliverable.id
        )
    )
    resolved_title = (title or "").strip()
    if not resolved_title:
        try:
            from app.scenarios.templates import get_sections_for_scenario

            for item in get_sections_for_scenario(project.scenario_package or "bidpilot"):
                if item.get("section_key") == section_key:
                    resolved_title = str(item.get("title") or section_key)
                    break
        except Exception:
            resolved_title = section_key
    if not resolved_title:
        resolved_title = section_key

    section = DeliverableSection(
        deliverable_id=deliverable.id,
        section_key=section_key,
        title=resolved_title,
        status="draft",
        sort_order=int(next_order or 0) + 1,
    )
    db.add(section)
    db.flush()
    return section


def write_section_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    """Directly write markdown into a section without the full draft workflow.

    Intended for empty-material / outline-first drafting when the user asks the
    agent to 自行拟草. Still goes through execute_capability (approval/audit).
    """
    from sqlalchemy import select

    project = require_project_capability(
        db,
        current_user=user,
        project_id=str(arguments.get("project_id") or "").strip(),
        capability="project.manage",
    ).project
    section_key = str(arguments.get("section_key") or "").strip()
    content = str(arguments.get("content_markdown") or "").strip()
    if not section_key:
        raise ValueError("section_key is required")
    if not content:
        raise ValueError("content_markdown is required")
    if len(content) > 50_000:
        raise ValueError("content_markdown is too long (max 50000 characters)")

    section = _find_or_create_section_for_write(
        db,
        project=project,
        section_key=section_key,
        deliverable_section_id=str(arguments.get("section_id") or "").strip() or None,
        title=str(arguments.get("title") or "").strip() or None,
    )
    latest = db.scalar(
        select(SectionVersion)
        .where(SectionVersion.deliverable_section_id == section.id)
        .order_by(SectionVersion.version_number.desc())
        .limit(1)
    )
    next_version = (latest.version_number + 1) if latest else 1
    version = SectionVersion(
        deliverable_section_id=section.id,
        version_number=next_version,
        content_markdown=content,
        created_by_actor="ai",
        generation_run_id=None,
    )
    db.add(version)
    section.status = "draft"
    db.commit()
    db.refresh(version)
    db.refresh(section)

    return AssistantToolResult(
        tool_name="write_section",
        result={
            "section_id": section.id,
            "section_key": section.section_key,
            "section_title": section.title,
            "section_version_id": version.id,
            "version_number": version.version_number,
            "deliverable_id": section.deliverable_id,
            "char_count": len(content),
        },
        summary=f"已写入章节「{section.title}」v{version.version_number}（{len(content)} 字）。",
    )


def run_section_campaign_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    """Process a bounded wave of empty outline sections (framework write or draft workflow).

    Designed for multi-section campaigns that resume across turns/wake notifications.
    Never tries to finish an entire bid book in one unbounded loop.
    """
    project_id = str(arguments.get("project_id") or "").strip()
    if not project_id:
        raise ValueError("project_id is required")
    mode = str(arguments.get("mode") or "framework").strip().lower()
    if mode not in {"framework", "draft_workflow", "plan"}:
        raise ValueError("mode must be plan, framework, or draft_workflow")
    raw_max = arguments.get("max_sections", 3)
    try:
        max_sections = int(raw_max)
    except (TypeError, ValueError):
        max_sections = 3
    max_sections = max(1, min(max_sections, 8))

    outline = get_project_outline(db, user, {"project_id": project_id})
    items = outline.result.get("items") if isinstance(outline.result, dict) else []
    if not isinstance(items, list):
        items = []

    requested_keys = arguments.get("section_keys")
    if isinstance(requested_keys, list) and requested_keys:
        wanted = {str(key).strip() for key in requested_keys if str(key).strip()}
        candidates = [
            item
            for item in items
            if isinstance(item, dict) and str(item.get("section_key") or "") in wanted
        ]
    else:
        candidates = [
            item
            for item in items
            if isinstance(item, dict) and not bool(item.get("has_content"))
        ]

    # auto_continue: process multiple waves in one capability call (bounded).
    auto_continue = bool(arguments.get("auto_continue"))
    if "auto_continue" not in arguments:
        # Default on for framework skeleton fills so "全部章节" can finish without
        # forcing the model to re-call for every remaining wave.
        auto_continue = mode == "framework"
    raw_max_waves = arguments.get("max_waves", 4 if auto_continue else 1)
    try:
        max_waves = int(raw_max_waves)
    except (TypeError, ValueError):
        max_waves = 4 if auto_continue else 1
    max_waves = max(1, min(max_waves, 6))

    processed_keys: list[str] = []
    written_keys: list[str] = []
    started_runtime_run_ids: list[str] = []
    failed: list[dict[str, str]] = []
    project_name = outline.result.get("project_name") if isinstance(outline.result, dict) else ""
    waves_run = 0
    remaining_keys: list[str] = []

    # Planner-worker split: plan mode only returns the ordered worklist.
    if mode == "plan":
        planned = [
            {
                "section_key": str(item.get("section_key") or ""),
                "title": str(item.get("title") or item.get("section_key") or ""),
                "has_content": bool(item.get("has_content")),
            }
            for item in candidates
            if isinstance(item, dict) and item.get("section_key")
        ]
        return AssistantToolResult(
            tool_name="run_section_campaign",
            result={
                "project_id": project_id,
                "mode": "plan",
                "processed_count": 0,
                "remaining_count": len(planned),
                "processed_section_keys": [],
                "remaining_section_keys": [item["section_key"] for item in planned],
                "planned_sections": planned,
                "written_section_keys": [],
                "started_runtime_run_ids": [],
                "failed": [],
                "has_more": len(planned) > 0,
                "waves_run": 0,
                "auto_continue": False,
            },
            summary=(
                f"多章节战役规划完成：待处理 {len(planned)} 章。"
                "下一步用 mode=framework 或 draft_workflow 执行。"
            ),
        )

    queue = list(candidates)
    while queue and waves_run < max_waves:
        wave = queue[:max_sections]
        queue = queue[max_sections:]
        waves_run += 1
        for item in wave:
            section_key = str(item.get("section_key") or "").strip()
            section_id = str(item.get("id") or "").strip() or None
            title = str(item.get("title") or section_key).strip() or section_key
            if not section_key:
                continue
            try:
                if mode == "framework":
                    skeleton = (
                        f"## {title}\n\n"
                        f"> 由多章节战役自动生成的框架草稿（项目：{project_name or project_id}）。\n\n"
                        "### 本章目标\n"
                        f"- 明确「{title}」需要回应的招标关注点\n"
                        "- 列出待补充的证据与数据\n\n"
                        "### 要点提纲\n"
                        "1. 背景与范围\n"
                        "2. 方案要点\n"
                        "3. 交付与保障\n\n"
                        "### 待补证据\n"
                        "- [ ] 相关资质 / 案例 / 指标\n"
                    )
                    write_section_tool(
                        db,
                        user,
                        {
                            "project_id": project_id,
                            "section_key": section_key,
                            "section_id": section_id,
                            "title": title,
                            "content_markdown": skeleton,
                        },
                    )
                    written_keys.append(section_key)
                else:
                    draft_args: dict[str, Any] = {
                        "project_id": project_id,
                        "section_key": section_key,
                        "section_id": section_id,
                    }
                    if arguments.get("provider_config_id"):
                        draft_args["provider_config_id"] = arguments.get("provider_config_id")
                    if arguments.get("reasoning_effort"):
                        draft_args["reasoning_effort"] = arguments.get("reasoning_effort")
                    if arguments.get("allow_empty_evidence"):
                        draft_args["allow_empty_evidence"] = True
                    if arguments.get("parent_runtime_run_id"):
                        draft_args["parent_runtime_run_id"] = arguments.get("parent_runtime_run_id")
                    started = start_draft_section(db, user, draft_args)
                    runtime_run_id = started.result.get("runtime_run_id")
                    if isinstance(runtime_run_id, str) and runtime_run_id:
                        started_runtime_run_ids.append(runtime_run_id)
                processed_keys.append(section_key)
            except Exception as exc:  # noqa: BLE001
                # A campaign can continue after one section fails, but raw
                # exceptions may contain provider, storage, or database details.
                # Persist only the stable runtime failure code for later retry.
                failure = classify_capability_failure(exc)
                failed.append(
                    {
                        "section_key": section_key,
                        "error_code": failure.error_code,
                    }
                )
        if not auto_continue:
            break

    remaining_keys = [
        str(item.get("section_key"))
        for item in queue
        if isinstance(item, dict) and item.get("section_key")
    ]
    result = {
        "project_id": project_id,
        "mode": mode,
        "processed_count": len(processed_keys),
        "remaining_count": len(remaining_keys),
        "processed_section_keys": processed_keys,
        "remaining_section_keys": remaining_keys,
        "written_section_keys": written_keys,
        "started_runtime_run_ids": started_runtime_run_ids,
        "failed": failed,
        "has_more": len(remaining_keys) > 0,
        "waves_run": waves_run,
        "auto_continue": auto_continue,
    }
    summary = (
        f"多章节战役（{mode}）完成 {waves_run} 波、处理 {len(processed_keys)} 章"
        + (f"，剩余 {len(remaining_keys)} 章" if remaining_keys else "，待写章节已清空")
        + (f"，失败 {len(failed)} 章" if failed else "")
        + "。"
    )
    return AssistantToolResult(
        tool_name="run_section_campaign",
        result=result,
        summary=summary,
        workflow=mode == "draft_workflow" and bool(started_runtime_run_ids),
    )


def start_draft_section(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    require_project_capability(
        db,
        current_user=user,
        project_id=arguments["project_id"],
        capability="workflow.run",
    )
    # Prefer evidence-backed drafts, but allow empty-project drafting so the
    # harness can still produce outline-first placeholder content when the user
    # explicitly asks to "自行拟草". The workflow itself handles zero evidence.
    from sqlalchemy import func, select

    from app.models import KnowledgeChunk

    chunk_count = db.scalar(
        select(func.count())
        .select_from(KnowledgeChunk)
        .where(KnowledgeChunk.project_id == arguments["project_id"])
    )
    allow_empty = bool(arguments.get("allow_empty_evidence"))
    if not chunk_count and not allow_empty:
        # Soft guidance rather than hard stop: still fail closed by default so
        # accidental drafts don't burn quota, but tell the model the escape hatch.
        raise ValueError(
            "当前项目还没有可检索的解析资料。若用户明确要求自行拟草/先写框架，"
            "请以 allow_empty_evidence=true 再次调用 start_draft_section；"
            "否则请先上传并等待资料包解析完成。"
        )
    response = draft_section_command(
        db,
        DraftSectionRequest(
            project_id=arguments["project_id"],
            section_key=arguments["section_key"],
            section_id=str(arguments.get("section_id") or "").strip() or None,
            provider_config_id=arguments.get("provider_config_id"),
            reasoning_effort=arguments.get("reasoning_effort"),
            parent_runtime_run_id=arguments.get("parent_runtime_run_id"),
        ),
        user,
    )
    return AssistantToolResult(
        tool_name="start_draft_section",
        result={
            **response.model_dump(),
            "project_id": arguments["project_id"],
            "section_key": arguments["section_key"],
        },
        summary=f"已启动章节起草工作流，运行 ID：{response.run_id}。",
        workflow=True,
    )


def submit_review_decision_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project_id = str(arguments.get("project_id") or "").strip()
    section_id = str(arguments.get("section_id") or "").strip()
    section_version_id = str(arguments.get("section_version_id") or "").strip()
    decision = str(arguments.get("decision") or "").strip().lower()
    if not project_id or not section_id or not section_version_id:
        raise ValueError("project_id, section_id, and section_version_id are required")
    if decision not in {"approved", "rejected"}:
        raise ValueError("decision must be approved or rejected")
    decision = canonical_review_decision(decision)
    section = require_deliverable_section_capability(
        db,
        current_user=user,
        section_id=section_id,
        capability="review.write",
    )
    deliverable = db.get(Deliverable, section.deliverable_id)
    if deliverable is None or deliverable.project_id != project_id:
        raise ValueError("Section does not belong to this project")
    review = submit_review_decision_command(
        db,
        ReviewDecisionCreate(
            section_id=section_id,
            section_version_id=section_version_id,
            decision=decision,
            comment=str(arguments.get("comment") or "").strip() or None,
        ),
        user,
    )
    summary = "章节审核已通过。" if review.decision == "approved" else "章节已退回修改。"
    return AssistantToolResult(
        tool_name="submit_review_decision",
        result={
            "section_id": review.section_id,
            "section_version_id": review.section_version_id,
            "decision": review.decision,
            "review_thread_id": review.id,
        },
        summary=summary,
    )


def search_bid_wiki_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    context = memory_context_for_agent(
        db,
        current_user=user,
        project_id=arguments.get("project_id"),
        query=str(arguments.get("query") or "").strip(),
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
    return AssistantToolResult(
        tool_name="search_bid_wiki",
        result={
            "memory_version": context.memory_version,
            "items": items,
            "degraded_reasons": list(context.degraded_reasons),
        },
        summary=f"找到 {len(items)} 条可用记忆。",
    )


def list_knowledge_portfolio_tool(db: Session, user: CurrentUser) -> AssistantToolResult:
    """Return the same aggregate-only view used by the Workbench portfolio.

    This deliberately does not construct a memory context pack. The Agent can
    help a user choose a project, but it must enter that project before reading
    any Bid Wiki record body or evidence.
    """
    items = [item.model_dump(mode="json") for item in list_memory_portfolio_query(db, user, limit=50)]
    return AssistantToolResult(
        tool_name="list_knowledge_portfolio",
        result={"items": items, "count": len(items)},
        summary=f"已检查 {len(items)} 个可访问项目的知识状态。",
    )


def propose_memory_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    scope = MemoryScope(arguments.get("scope", MemoryScope.USER_PRIVATE.value))
    record = create_memory_command(
        db,
        MemoryCreate(
            scope=scope,
            project_id=arguments.get("project_id"),
            kind=MemoryKind(arguments.get("kind", MemoryKind.PREFERENCE.value)),
            title=str(arguments.get("title") or "个人工作偏好").strip(),
            body_markdown=str(arguments.get("body_markdown") or "").strip(),
        ),
        user,
    )
    summary = "已保存为个人工作偏好。" if scope is MemoryScope.USER_PRIVATE else "已提交到项目知识审核队列。"
    return AssistantToolResult(
        tool_name="propose_memory",
        result={"id": record.id, "status": record.status.value, "scope": record.scope.value},
        summary=summary,
    )


def propose_memory_graph_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project_id = str(arguments.get("project_id") or "").strip()
    memory_record_id = str(arguments.get("memory_record_id") or "").strip()
    if not project_id or not memory_record_id:
        raise ValueError("project_id and memory_record_id are required")

    response = start_memory_graph_extraction_command(
        db,
        MemoryGraphExtractionCreate(
            project_id=project_id,
            memory_record_id=memory_record_id,
            provider_config_id=arguments.get("provider_config_id"),
            reasoning_effort=arguments.get("reasoning_effort"),
        ),
        user,
    )
    summary = "已复用正在处理的实体关系提案。" if response.reused else "实体关系提案已启动，完成后会进入项目知识审核队列。"
    return AssistantToolResult(
        tool_name="propose_memory_graph",
        result={
            "run_id": response.run_id,
            "runtime_run_id": response.runtime_run_id,
            "status": response.status,
            "reused": response.reused,
        },
        summary=summary,
        workflow=True,
    )


def forget_memory_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    memory_id = str(arguments.get("memory_id") or "").strip()
    if not memory_id:
        raise ValueError("memory_id is required")
    delete_memory_command(db, memory_id, user)
    return AssistantToolResult(
        tool_name="forget_memory",
        result={"deleted": True, "memory_id": memory_id},
        summary="这条记忆已遗忘。",
    )


def start_redraft_section(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    require_project_capability(
        db,
        current_user=user,
        project_id=arguments["project_id"],
        capability="workflow.run",
    )
    response = redraft_section_command(
        db,
        RedraftSectionRequest(
            project_id=arguments["project_id"],
            section_key=arguments["section_key"],
            section_id=str(arguments.get("section_id") or "").strip() or None,
            review_feedback=arguments.get("review_feedback"),
            provider_config_id=arguments.get("provider_config_id"),
            reasoning_effort=arguments.get("reasoning_effort"),
            parent_runtime_run_id=arguments.get("parent_runtime_run_id"),
        ),
        user,
    )
    return AssistantToolResult(
        tool_name="start_redraft_section",
        result={
            **response.model_dump(),
            "project_id": arguments["project_id"],
            "section_key": arguments["section_key"],
        },
        summary=f"已启动章节重写工作流，运行 ID：{response.run_id}。",
        workflow=True,
    )


def resume_draft_run_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    """Resume a drafting run that is paused for human approval."""
    run_id = str(arguments.get("run_id") or "").strip()
    decision = str(arguments.get("decision") or "").strip()
    if not run_id:
        raise ValueError("run_id is required")
    if decision not in {"approved", "rejected"}:
        raise ValueError("decision must be approved or rejected")
    feedback = arguments.get("feedback")
    response = resume_run_command(
        db,
        run_id,
        ResumeRunRequest(
            decision=decision,  # type: ignore[arg-type]
            feedback=str(feedback) if feedback is not None else None,
        ),
        user,
    )
    return AssistantToolResult(
        tool_name="resume_draft_run",
        result=response.model_dump(),
        summary=f"已提交章节审核决定，运行 ID：{response.run_id}。",
        workflow=True,
    )


def _get_project_for_user(db: Session, user: CurrentUser, project_id: str) -> Project:
    return require_project_capability(
        db,
        current_user=user,
        project_id=project_id,
        capability="project.read",
    ).project


# ── New read-only tools ──────────────────────────────────────────────────────


def list_requirements_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project = _get_project_for_user(db, user, arguments["project_id"])
    items = list_requirements_query(db, project.id, current_user=user)
    return AssistantToolResult(
        tool_name="list_requirements",
        result={"items": [item.model_dump() for item in items]},
        summary=f"项目「{project.name}」下有 {len(items)} 条需求。",
    )


def list_evidence_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project = _get_project_for_user(db, user, arguments["project_id"])
    items = list_evidence_query(db, project.id, user)
    return AssistantToolResult(
        tool_name="list_evidence",
        result={"items": [item.model_dump() for item in items]},
        summary=f"项目「{project.name}」下有 {len(items)} 条证据。",
    )


def list_deliverables_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project = _get_project_for_user(db, user, arguments["project_id"])
    items = list_deliverables_query(db, project.id, user)
    return AssistantToolResult(
        tool_name="list_deliverables",
        result={"items": [item.model_dump() for item in items]},
        summary=f"项目「{project.name}」下有 {len(items)} 个交付物。",
    )


def list_documents_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project = _get_project_for_user(db, user, arguments["project_id"])
    bundle_id = arguments.get("bundle_id")
    if bundle_id:
        bundle = require_bundle_capability(
            db,
            current_user=user,
            bundle_id=bundle_id,
            capability="project.read",
        )
        if bundle.project_id != project.id:
            raise ValueError("Bundle does not belong to this project")
        document_rows = [(bundle.label, bundle.ingest_status, item) for item in list_documents_query(db, bundle_id, user)]
    else:
        document_rows = []
        for bundle in list_bundles_query(db, project.id, current_user=user):
            document_rows.extend(
                (bundle.label, bundle.ingest_status, item)
                for item in list_documents_query(db, bundle.id, user)
            )
    return AssistantToolResult(
        tool_name="list_documents",
        result={
            "items": [
                {
                    **item.model_dump(),
                    "bundle_label": bundle_label,
                    "bundle_status": bundle_status,
                }
                for bundle_label, bundle_status, item in document_rows
            ]
        },
        summary=f"找到 {len(document_rows)} 个文档。",
    )


def list_claim_review_queue_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project = _get_project_for_user(db, user, arguments["project_id"])
    queue = get_claim_review_queue_query(db, project.id, current_user=user)
    result = {
        "project_id": queue.project_id,
        "count": queue.count,
        "ready_to_verify_count": queue.ready_to_verify_count,
        "blocked_by_evidence_count": queue.blocked_by_evidence_count,
        "truncated": queue.truncated,
    }
    if queue.count == 0:
        summary = f"项目「{project.name}」目前没有待人工核验的 AI 主张。"
    else:
        summary = (
            f"项目「{project.name}」有 {queue.count} 条 AI 主张等待人工核验，"
            f"其中 {queue.ready_to_verify_count} 条已具备核验条件，"
            f"{queue.blocked_by_evidence_count} 条仍缺少已核验证据。"
        )
    return AssistantToolResult(
        tool_name="list_claim_review_queue",
        result=result,
        summary=summary,
    )


def attach_uploaded_documents_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project_id = str(arguments.get("project_id") or "").strip()
    attachment_ids = arguments.get("attachment_ids")
    if not project_id:
        raise ValueError("project_id is required")
    if not isinstance(attachment_ids, list) or not all(isinstance(item, str) and item for item in attachment_ids):
        raise ValueError("attachment_ids must be a non-empty list of staged attachment ids")
    result = attach_staged_attachments_to_project(
        db,
        current_user=user,
        project_id=project_id,
        attachment_ids=attachment_ids,
        bundle_label=arguments.get("bundle_label"),
    )
    attachment_count = result.get("attachment_count")
    if not isinstance(attachment_count, int):
        raise RuntimeError("attachment staging returned an invalid attachment count")
    summary = (
        f"已将 {attachment_count} 个附件加入资料包，并开始解析。"
        if result.get("ingest_queued") is not False
        else f"已将 {attachment_count} 个附件加入资料包；解析任务等待重新提交。"
    )
    return AssistantToolResult(
        tool_name="attach_uploaded_documents",
        result=result,
        summary=summary,
    )


def get_section_versions_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project = _get_project_for_user(db, user, arguments["project_id"])
    section_id = arguments.get("section_id", "")
    if section_id:
        section = require_deliverable_section_capability(
            db,
            current_user=user,
            section_id=section_id,
            capability="project.read",
        )
        deliverable = db.get(Deliverable, section.deliverable_id)
        if deliverable is None or deliverable.project_id != project.id:
            raise ValueError("Section does not belong to this project")
    items = list_versions_query(db, section_id, user) if section_id else []
    return AssistantToolResult(
        tool_name="get_section_versions",
        result={"items": [item.model_dump() for item in items]},
        summary=f"找到 {len(items)} 个版本。",
    )


# ── New mutation tools ───────────────────────────────────────────────────────


def create_deliverable_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project = require_project_capability(
        db,
        current_user=user,
        project_id=arguments["project_id"],
        capability="project.manage",
    ).project
    title = str(arguments.get("title") or "").strip()
    if not title:
        raise ValueError("Deliverable title is required")
    deliverable = create_deliverable_command(
        db,
        DeliverableCreate(project_id=project.id, type=arguments.get("type", "proposal"), title=title),
        user,
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
    require_execution_run_capability(
        db,
        current_user=user,
        run_id=run_id,
        capability="workflow.run",
    )
    run = retry_failed_run_command(db, run_id, user)
    return AssistantToolResult(
        tool_name="retry_run",
        result=run.model_dump(),
        summary=f"已创建新的重试运行 {run.id[:8]}。",
    )


def get_readiness_summary_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project = _get_project_for_user(db, user, arguments["project_id"])
    summary = get_readiness_summary_query(db, project.id, current_user=user)
    return AssistantToolResult(
        tool_name="get_readiness_summary",
        result={
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
        summary=(
            f"项目「{summary.project_name}」当前就绪度为 {summary.readiness_score:.1f} 分，"
            f"有 {len(summary.mandatory_gaps)} 个强制项缺口和 {len(summary.evidence_gaps)} 个证据缺口。"
        ),
    )


def list_readiness_gaps_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project = _get_project_for_user(db, user, arguments["project_id"])
    kind = _normalize_readiness_gap_kind(arguments.get("kind"))
    summary = get_readiness_summary_query(db, project.id, current_user=user)
    items = select_readiness_gaps(summary, kind=kind)[:20]
    return AssistantToolResult(
        tool_name="list_readiness_gaps",
        result={
            "kind": kind,
            "items": [_readiness_gap_to_result(item) for item in items],
        },
        summary=f"项目「{summary.project_name}」有 {len(items)} 个{_readiness_gap_label(kind)}。",
    )


def open_requirement_source_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    requirement_id = str(arguments.get("requirement_id") or "")
    if not requirement_id:
        raise ValueError("requirement_id is required")
    requirement = get_requirement_query(db, requirement_id, current_user=user)
    result = {
        "id": requirement.id,
        "requirement_text": requirement.requirement_text,
        "original_text": requirement.original_text,
        "source_document_name": requirement.source_document_name,
        "source_locator_json": requirement.source_locator_json,
        "verification_status": requirement.verification_status,
        "coverage_status": requirement.bid_profile.coverage_status if requirement.bid_profile else "uncovered",
    }
    if requirement.source_locator_json:
        summary = f"已定位需求「{requirement.requirement_text[:32]}」的来源定位。"
    else:
        summary = f"需求「{requirement.requirement_text[:32]}」尚未关联来源定位。"
    return AssistantToolResult(
        tool_name="open_requirement_source",
        result=result,
        summary=summary,
    )


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


def _normalize_readiness_gap_kind(value: object) -> str:
    """Accept common model/user phrasing without turning a read into a failed run."""
    raw = str(value or "all").strip().casefold().replace("-", "_").replace(" ", "_")
    aliases = {
        "requirements": "mandatory",
        "requirement": "mandatory",
        "requirement_gap": "mandatory",
        "requirement_gaps": "mandatory",
        "mandatory_gaps": "mandatory",
        "evidence_gap": "evidence",
        "evidence_gaps": "evidence",
        "风险": "high_risk",
        "高风险": "high_risk",
        "强制项": "mandatory",
        "需求": "mandatory",
        "证据": "evidence",
        "矛盾": "contradictions",
        "逾期": "overdue",
        "未覆盖": "uncovered",
    }
    normalized = aliases.get(raw, raw)
    return normalized if normalized in READINESS_GAP_KINDS else "all"


def _readiness_gap_label(kind: str) -> str:
    return {
        "high_risk": "高风险缺口",
        "mandatory": "强制项缺口",
        "evidence": "证据缺口",
        "contradictions": "矛盾项",
        "overdue": "逾期项",
        "uncovered": "未覆盖项",
    }.get(kind, "待处理缺口")


def export_deliverable_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    deliverable_id = arguments.get("deliverable_id", "")
    fmt = arguments.get("format", "docx")
    if not deliverable_id:
        raise ValueError("deliverable_id is required")
    deliverable = require_deliverable_capability(
        db,
        current_user=user,
        deliverable_id=deliverable_id,
        capability="deliverables.export",
    )
    # Prefer server-derived project ownership. If the model supplies project_id,
    # it must match; if omitted, use the deliverable's project.
    requested_project_id = arguments.get("project_id")
    if requested_project_id and deliverable.project_id != requested_project_id:
        raise ValueError("Deliverable does not belong to this project")
    # Partial packages are allowed when at least one approved section exists.
    # generate_deliverable_export_command enforces that content boundary.
    if deliverable.status not in {"approved", "in_review", "draft"}:
        raise ValueError(f"Deliverable status '{deliverable.status}' cannot be exported")
    artifact = generate_deliverable_export_command(
        db,
        deliverable_id=deliverable_id,
        artifact_format=str(fmt).lower(),
        current_user=user,
        require_approved=True,
    )
    return AssistantToolResult(
        tool_name="export_deliverable",
        result={
            "project_id": deliverable.project_id,
            "deliverable_id": deliverable_id,
            "deliverable_title": deliverable.title,
            "export_id": artifact.export_id,
            "format": str(fmt).lower(),
            "status": "ready",
            "download_path": artifact.download_path,
            "persisted": artifact.storage_key is not None,
        },
        summary=f"交付物「{deliverable.title}」的 {str(fmt).upper()} 已生成，可下载。",
    )


def generate_readiness_pack_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project_id = str(arguments.get("project_id") or "").strip()
    if not project_id:
        raise ValueError("project_id is required")
    pack = generate_readiness_pack_command(
        db,
        project_id,
        current_user=user,
        actor_id=user.id,
    )
    return AssistantToolResult(
        tool_name="generate_readiness_pack",
        result={
            "pack_id": pack.id,
            "version_number": pack.version_number,
            "status": pack.status,
            "xlsx_download_path": f"/readiness/packs/{pack.id}/xlsx",
            "docx_download_path": f"/readiness/packs/{pack.id}/docx",
        },
        summary=f"投标准备度包 v{pack.version_number} 已生成，可下载 DOCX 和 XLSX。",
    )


def delete_project_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    project = require_project_capability(
        db,
        current_user=user,
        project_id=arguments["project_id"],
        capability="project.delete",
    ).project
    name = project.name
    confirmation_text = str(arguments.get("confirmation_text") or "").strip()
    if confirmation_text != name:
        raise ValueError(f"删除项目需要输入完整项目名称「{name}」进行确认。")
    delete_project_command_for_user(db, project.id, user)
    return AssistantToolResult(
        tool_name="delete_project",
        result={"deleted": True, "project_id": arguments["project_id"], "name": name},
        summary=f"项目「{name}」已删除。",
    )


def semantic_search_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    """Project-scoped evidence retrieval (same path as /retrieval/search)."""
    from app.retrieval.service import search_knowledge

    project_id = str(arguments.get("project_id") or "").strip()
    query = str(arguments.get("query") or "").strip()
    if not project_id or not query:
        raise ValueError("project_id and query are required")
    top_k = arguments.get("top_k")
    try:
        k = int(top_k) if top_k is not None else 8
    except (TypeError, ValueError):
        k = 8
    k = max(1, min(k, 20))
    response = search_knowledge(
        db,
        project_id=project_id,
        query=query,
        current_user=user,
        top_k=k,
    )
    items = [
        {
            "chunk_id": item.chunk_id,
            "source_document_id": item.source_document_id,
            "score": item.score,
            "excerpt": (item.content or "")[:400],
            "heading": item.citation.heading if item.citation else None,
            "page": item.citation.page if item.citation else None,
        }
        for item in response.results[:k]
    ]
    return AssistantToolResult(
        tool_name="semantic_search",
        result={
            "project_id": response.project_id,
            "count": len(items),
            "items": items,
            "degraded_reasons": list(response.degraded_reasons or ()),
        },
        summary=f"检索到 {len(items)} 条相关资料片段。",
    )


def start_deep_research_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    """Queue the generic Deep Research runtime from a governed Pi action."""
    from app.runtime.deep_research_control import create_deep_research_run

    parent_run_id = str(arguments.get("parent_runtime_run_id") or "").strip()
    tool_call_id = str(arguments.get("tool_call_id") or "deep-research-action").strip()
    if not parent_run_id:
        raise ValueError("deep_research_parent_run_required")
    result = create_deep_research_run(
        db,
        user,
        parent_run_id=parent_run_id,
        tool_call_id=tool_call_id,
        arguments=arguments,
    )
    return AssistantToolResult(
        tool_name="start_deep_research",
        result=result,
        summary="深度调研已启动，将按计划并行检索、核验来源并生成报告。",
    )


def web_search_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    """External web search for research tasks.

    Prefer the configured Hikari Tavily gateway when present. The gateway uses
    a Bearer token and a ``/search`` endpoint; the official Tavily endpoint
    instead receives its key in the JSON body. Keeping these wire contracts
    separate prevents an aggregator token from being sent as an official key.
    Without either configuration, fall back to DuckDuckGo for local/dev.
    """
    import os

    import httpx

    _ = db, user  # auth already enforced at capability boundary
    query = str(arguments.get("query") or "").strip()
    if not query:
        raise ValueError("query is required")
    max_results = arguments.get("max_results")
    try:
        limit = int(max_results) if max_results is not None else 5
    except (TypeError, ValueError):
        limit = 5
    limit = max(1, min(limit, 10))
    topic = str(arguments.get("topic") or "general").strip().lower()
    if topic not in {"general", "news", "finance"}:
        topic = "general"
    search_depth = str(arguments.get("search_depth") or "basic").strip().lower()
    if search_depth not in {"basic", "advanced"}:
        search_depth = "basic"
    include_raw_content = bool(arguments.get("include_raw_content") is True)

    tavily_key = (
        os.environ.get("DOCPILOT_TAVILY_API_KEY")
        or os.environ.get("TAVILY_API_KEY")
        or ""
    ).strip()
    tavily_base_url = (
        os.environ.get("TAVILY_HIKARI_BASE_URL")
        or os.environ.get("TAVILY_API_BASE_URL")
        or ""
    ).strip().rstrip("/")
    hikari_token = (os.environ.get("TAVILY_HIKARI_TOKEN") or tavily_key).strip()
    items: list[dict] = []
    provider = "duckduckgo"

    if tavily_base_url or tavily_key:
        provider = "tavily_hikari" if tavily_base_url else "tavily"
        endpoint = (
            tavily_base_url if tavily_base_url.endswith("/search") else f"{tavily_base_url}/search"
        ) if tavily_base_url else "https://api.tavily.com/search"
        request_headers = {"Authorization": f"Bearer {hikari_token}"} if tavily_base_url and hikari_token else {}
        request_body = {
            "query": query,
            "max_results": limit,
            "include_answer": False,
            "search_depth": search_depth,
            "topic": topic,
            "include_raw_content": include_raw_content,
        }
        if not tavily_base_url:
            request_body["api_key"] = tavily_key
        resp = httpx.post(
            endpoint,
            headers=request_headers,
            json=request_body,
            timeout=20.0,
        )
        resp.raise_for_status()
        payload = resp.json()
        for row in (payload.get("results") or [])[:limit]:
            if not isinstance(row, dict):
                continue
            items.append(
                {
                    "title": str(row.get("title") or "")[:200],
                    "url": str(row.get("url") or "")[:500],
                    "snippet": str(row.get("content") or row.get("snippet") or "")[:500],
                    **({"raw_content": str(row.get("raw_content") or "")[:4_000]} if include_raw_content and row.get("raw_content") else {}),
                }
            )
    else:
        # Key-free fallback for local/dev; quality is lower than Tavily.
        resp = httpx.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            timeout=15.0,
            headers={"User-Agent": "BidPilotAgent/1.0"},
        )
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload.get("AbstractText"), str) and payload.get("AbstractURL"):
            items.append(
                {
                    "title": str(payload.get("Heading") or query)[:200],
                    "url": str(payload.get("AbstractURL"))[:500],
                    "snippet": str(payload.get("AbstractText"))[:500],
                }
            )
        for row in (payload.get("RelatedTopics") or [])[:limit]:
            if not isinstance(row, dict):
                continue
            text = str(row.get("Text") or "")
            url = str(row.get("FirstURL") or "")
            if not text or not url:
                continue
            items.append({"title": text[:120], "url": url[:500], "snippet": text[:500]})
            if len(items) >= limit:
                break

    return AssistantToolResult(
        tool_name="web_search",
        result={"query": query, "provider": provider, "topic": topic, "search_depth": search_depth, "count": len(items), "items": items},
        summary=f"联网搜索「{query}」返回 {len(items)} 条结果（{provider}）。",
    )


def discover_remote_documents_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    """Find direct tender-file links on one public page without persisting it."""
    from app.documents.web_import import discover_remote_documents

    url = str(arguments.get("url") or "").strip()
    if not url:
        raise ValueError("url is required")
    project_id = str(arguments.get("project_id") or "").strip()
    if project_id:
        require_project_capability(
            db,
            current_user=user,
            project_id=project_id,
            capability="project.read",
        )
    try:
        max_results = int(arguments.get("max_results") or 10)
    except (TypeError, ValueError):
        max_results = 10
    candidates = discover_remote_documents(url, max_results=max_results)
    items = [
        {
            "url": candidate.url,
            "filename": candidate.filename,
            "title": candidate.title,
            "content_type_hint": candidate.content_type_hint,
        }
        for candidate in candidates
    ]
    return AssistantToolResult(
        tool_name="discover_remote_documents",
        result={"url": url, "count": len(items), "items": items},
        summary=(
            f"在公开页面发现 {len(items)} 个可能的直接资料附件；"
            "未下载、未写入项目。确认具体文件后再入库。"
            if items
            else "该页面没有发现可识别的直接资料附件；未下载、未写入项目。"
        ),
    )


def _resolve_upload_bundle(db: Session, user: CurrentUser, project_id: str, bundle_id: str | None) -> str:
    from app.bundles.service import list_bundles_query
    from app.models import Bundle

    if bundle_id:
        require_bundle_capability(
            db,
            current_user=user,
            bundle_id=bundle_id,
            capability="bundles.write",
        )
        return bundle_id
    bundles = list_bundles_query(db, project_id, current_user=user)
    for bundle in bundles:
        if getattr(bundle, "ingest_status", None) not in {"queued", "running", "indexing"}:
            return bundle.id
    # Create a dedicated agent uploads bundle when none is writable.
    require_project_capability(
        db,
        current_user=user,
        project_id=project_id,
        capability="bundles.write",
    )
    bundle = Bundle(
        project_id=project_id,
        label="Agent uploads",
        source_type="upload",
        ingest_status="ready_to_ingest",
    )
    db.add(bundle)
    db.commit()
    db.refresh(bundle)
    return bundle.id


def fetch_url_to_project_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    """Persist one chosen remote artifact or explicitly requested web evidence."""
    import hashlib

    from app.documents.service import upload_document_command
    from app.documents.web_import import download_web_source
    from app.models import Bundle

    project_id = str(arguments.get("project_id") or "").strip()
    url = str(arguments.get("url") or "").strip()
    import_mode_value = str(arguments.get("import_mode") or "artifact").strip().lower()
    if not project_id or not url:
        raise ValueError("project_id and url are required")
    if import_mode_value not in {"artifact", "web_evidence"}:
        raise ValueError("import_mode must be artifact or web_evidence")
    import_mode = cast(Literal["artifact", "web_evidence"], import_mode_value)
    require_project_capability(
        db,
        current_user=user,
        project_id=project_id,
        capability="bundles.write",
    )
    parent_runtime_run_id = str(arguments.get("parent_runtime_run_id") or "").strip() or None
    bundle_id = _resolve_upload_bundle(
        db,
        user,
        project_id,
        str(arguments.get("bundle_id") or "").strip() or None,
    )

    # Artifact downloads can be hundreds of megabytes.  When the request came
    # from the governed Agent runtime, persist a child run and return
    # immediately; the worker owns the slow network and storage operation.
    # Direct service calls without a parent run retain the synchronous path for
    # API compatibility and small administrative imports.
    if import_mode == "artifact" and parent_runtime_run_id:
        from app.celery_client import celery
        from app.runtime.events import RuntimeEventDraft, publish_event
        from app.runtime.repository import get_visible_runtime_run
        from app.runtime.service import create_or_get_runtime_run, fail_runtime_run
        from contracts.runtime import RuntimeEventType

        parent = get_visible_runtime_run(db, parent_runtime_run_id, user)
        if parent.user_id != user.id and user.role != "admin":
            raise ValueError("远程导入任务只能挂到当前用户的 Agent 运行上")

        idempotency_key = (
            "remote-import:"
            f"{parent_runtime_run_id}:{project_id}:{bundle_id}:"
            f"{hashlib.sha256(url.encode('utf-8')).hexdigest()}"
        )
        creation = create_or_get_runtime_run(
            db,
            user,
            kind="remote_import",
            engine="remote_import_worker",
            project_id=project_id,
            conversation_id=parent.conversation_id,
            parent_run_id=parent_runtime_run_id,
            idempotency_key=idempotency_key,
            input_json={
                "project_id": project_id,
                "bundle_id": bundle_id,
                "url": url,
                "filename": str(arguments.get("filename") or "").strip() or None,
                "import_mode": import_mode,
            },
        )
        child = creation.run
        if child.status in {"succeeded", "failed", "cancelled", "expired"}:
            if child.status == "succeeded" and isinstance(child.result_json, dict):
                return AssistantToolResult(
                    tool_name="fetch_url_to_project",
                    result={**child.result_json, "status": child.status, "runtime_run_id": child.id},
                    summary="远程资料已完成入库；已复用此前相同地址的导入结果。",
                )
            raise ValueError(child.error_message or "该远程资料导入任务已结束，请重新发起。")
        if creation.created:
            try:
                publish_event(
                    db,
                    parent.id,
                    RuntimeEventDraft(
                        type=RuntimeEventType.WORKFLOW_LINKED,
                        public_summary="已创建远程资料后台导入任务。",
                        payload={
                            "workflow_runtime_run_id": child.id,
                            "remote_import_runtime_run_id": child.id,
                            "source_url": url,
                        },
                    ),
                )
                celery.send_task("worker.import_remote_document", args=[child.id])
            except Exception as exc:  # noqa: BLE001
                fail_runtime_run(db, child.id, "后台导入任务未能排队，请稍后重试。", error_code="remote_import_queue_failed")
                raise RuntimeError("后台导入任务未能排队，请稍后重试。") from exc
        return AssistantToolResult(
            tool_name="fetch_url_to_project",
            result={
                "status": "queued",
                "runtime_run_id": child.id,
                "project_id": project_id,
                "bundle_id": bundle_id,
                "source_url": url,
                "import_mode": import_mode,
            },
            summary="已开始后台下载远程资料。完成后会自动写入项目资料包；你可以继续使用当前对话。",
        )

    downloaded = download_web_source(
        url,
        filename=str(arguments.get("filename") or "").strip() or None,
        import_mode=import_mode,
    )

    doc = upload_document_command(
        db,
        bundle_id=bundle_id,
        filename=downloaded.filename,
        content_type=downloaded.content_type,
        data=downloaded.data,
        current_user=user,
        source_url=downloaded.source_url,
    )
    bundle = db.get(Bundle, bundle_id)
    ingest_queued = doc.ingest_queued
    stored_as_artifact = doc.parse_status == "not_applicable"
    return AssistantToolResult(
        tool_name="fetch_url_to_project",
        result={
            "project_id": project_id,
            "bundle_id": bundle_id,
            "bundle_label": bundle.label if bundle is not None else "项目资料包",
            "document_id": doc.id,
            "filename": doc.original_filename,
            "bytes": len(downloaded.data),
            "source_url": downloaded.source_url,
            "import_mode": import_mode,
            "parse_status": doc.parse_status,
            "ingest_queued": ingest_queued,
            "storage_status": "stored_no_parse" if stored_as_artifact else "queued_for_ingestion",
        },
        summary=(
            f"已将「{doc.original_filename}」作为{('网页研究证据' if import_mode == 'web_evidence' else '远程资料文件')}"
            f"加入项目资料包；"
            + (
                "该资料已归档，可下载使用；当前格式不参与文本解析。"
                if stored_as_artifact
                else ("已投递解析。" if ingest_queued else "解析任务暂未投递，可在资料中心重试。")
            )
        ),
    )


def upload_document_tool(db: Session, user: CurrentUser, arguments: dict) -> AssistantToolResult:
    """Ingest staged chat attachments or raw content into a project bundle.

    Preferred agent path: pass ``attachment_ids`` from chat uploads.
    Alternate path: ``content_base64`` + ``filename`` for small agent-generated files.
    """
    import base64

    from app.documents.service import upload_document_command

    project_id = str(arguments.get("project_id") or "").strip()
    if not project_id:
        raise ValueError("project_id is required")

    attachment_ids = arguments.get("attachment_ids")
    if isinstance(attachment_ids, list) and attachment_ids:
        return attach_uploaded_documents_tool(
            db,
            user,
            {
                "project_id": project_id,
                "attachment_ids": attachment_ids,
                "bundle_label": arguments.get("bundle_label") or "AI uploads",
            },
        )

    content_b64 = str(arguments.get("content_base64") or "").strip()
    filename = str(arguments.get("filename") or "").strip() or "upload.bin"
    if not content_b64:
        raise ValueError(
            "Provide attachment_ids (from chat uploads) or content_base64+filename. "
            "Browser file pickers still go through the UI upload control."
        )
    try:
        data = base64.b64decode(content_b64, validate=True)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("content_base64 is not valid base64") from exc
    if len(data) > 10 * 1024 * 1024:
        raise ValueError("content_base64 payload too large (max 10MB)")

    require_project_capability(
        db,
        current_user=user,
        project_id=project_id,
        capability="bundles.write",
    )
    bundle_id = _resolve_upload_bundle(
        db,
        user,
        project_id,
        str(arguments.get("bundle_id") or "").strip() or None,
    )
    content_type = str(arguments.get("content_type") or "application/octet-stream")
    doc = upload_document_command(
        db,
        bundle_id=bundle_id,
        filename=filename[:200],
        content_type=content_type,
        data=data,
        current_user=user,
    )
    return AssistantToolResult(
        tool_name="upload_document",
        result={
            "project_id": project_id,
            "bundle_id": bundle_id,
            "document_id": doc.id,
            "filename": doc.original_filename,
            "bytes": len(data),
            "parse_status": doc.parse_status,
        },
        summary=f"已上传「{doc.original_filename}」到项目资料包。",
    )
