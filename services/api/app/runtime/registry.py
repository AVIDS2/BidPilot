"""Product capability metadata and public result formatting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contracts.runtime import RuntimeRiskLevel


@dataclass(frozen=True)
class CapabilityDefinition:
    name: str
    label_zh: str
    label_en: str
    risk_level: RuntimeRiskLevel
    required_project_capability: str | None = None
    requires_approval_in_risky_only: bool = False
    requires_typed_confirmation: bool = False


@dataclass(frozen=True)
class PublicCapabilityResult:
    summary: str
    payload: dict[str, Any]


_CAPABILITIES = (
    CapabilityDefinition("search_projects", "搜索项目", "Search projects", RuntimeRiskLevel.READ),
    CapabilityDefinition(
        "create_demo_workspace",
        "创建演示工作区",
        "Create demo workspace",
        RuntimeRiskLevel.LOW_RISK_WRITE,
        requires_approval_in_risky_only=True,
    ),
    CapabilityDefinition(
        "create_project",
        "创建项目",
        "Create project",
        RuntimeRiskLevel.LOW_RISK_WRITE,
        requires_approval_in_risky_only=True,
    ),
    CapabilityDefinition("get_project_summary", "查看项目概览", "Get project summary", RuntimeRiskLevel.READ, "project.read"),
    CapabilityDefinition("list_project_bundles", "查看资料包", "List project bundles", RuntimeRiskLevel.READ, "project.read"),
    CapabilityDefinition("list_sections", "查看章节", "List sections", RuntimeRiskLevel.READ, "project.read"),
    CapabilityDefinition(
        "get_project_outline",
        "查看项目大纲",
        "Get project outline",
        RuntimeRiskLevel.READ,
        "project.read",
    ),
    CapabilityDefinition("list_pending_reviews", "查看待审内容", "List pending reviews", RuntimeRiskLevel.READ, "project.read"),
    CapabilityDefinition(
        "submit_review_decision",
        "提交章节审核决定",
        "Submit section review decision",
        RuntimeRiskLevel.LOW_RISK_WRITE,
        "review.write",
        requires_approval_in_risky_only=True,
    ),
    CapabilityDefinition("list_requirements", "查看需求", "List requirements", RuntimeRiskLevel.READ, "project.read"),
    CapabilityDefinition(
        "list_claim_review_queue",
        "查看待核验主张",
        "List claims awaiting review",
        RuntimeRiskLevel.READ,
        "project.read",
    ),
    CapabilityDefinition("get_readiness_summary", "查看投标准备度", "Get bid readiness", RuntimeRiskLevel.READ, "project.read"),
    CapabilityDefinition("list_readiness_gaps", "查看就绪缺口", "List readiness gaps", RuntimeRiskLevel.READ, "project.read"),
    CapabilityDefinition("open_requirement_source", "定位需求来源", "Open requirement source", RuntimeRiskLevel.READ, "project.read"),
    CapabilityDefinition("list_evidence", "查看证据", "List evidence", RuntimeRiskLevel.READ, "project.read"),
    CapabilityDefinition("list_deliverables", "查看交付物", "List deliverables", RuntimeRiskLevel.READ, "project.read"),
    CapabilityDefinition("list_documents", "查看文档", "List documents", RuntimeRiskLevel.READ, "project.read"),
    CapabilityDefinition(
        "attach_uploaded_documents",
        "将附件加入项目资料包",
        "Ingest uploaded attachments",
        RuntimeRiskLevel.COSTING,
        "bundles.write",
        requires_approval_in_risky_only=True,
    ),
    CapabilityDefinition("get_section_versions", "查看章节版本", "Get section versions", RuntimeRiskLevel.READ, "project.read"),
    CapabilityDefinition(
        "create_deliverable",
        "创建交付物",
        "Create deliverable",
        RuntimeRiskLevel.LOW_RISK_WRITE,
        "project.manage",
        requires_approval_in_risky_only=True,
    ),
    CapabilityDefinition(
        "start_draft_section",
        "启动章节起草",
        "Start draft section",
        RuntimeRiskLevel.COSTING,
        "workflow.run",
        requires_approval_in_risky_only=True,
    ),
    CapabilityDefinition(
        "write_section",
        "直接写入章节内容",
        "Write section markdown",
        RuntimeRiskLevel.LOW_RISK_WRITE,
        "project.manage",
        requires_approval_in_risky_only=True,
    ),
    CapabilityDefinition(
        "start_redraft_section",
        "启动章节重写",
        "Start redraft section",
        RuntimeRiskLevel.COSTING,
        "workflow.run",
        requires_approval_in_risky_only=True,
    ),
    CapabilityDefinition(
        "resume_draft_run",
        "恢复章节审核工作流",
        "Resume draft run after human approval",
        RuntimeRiskLevel.LOW_RISK_WRITE,
        "workflow.run",
        requires_approval_in_risky_only=True,
    ),
    CapabilityDefinition(
        "propose_memory_graph",
        "生成实体关系提案",
        "Generate entity-relation proposal",
        RuntimeRiskLevel.COSTING,
        "memory.approve",
        requires_approval_in_risky_only=True,
    ),
    CapabilityDefinition("get_runtime_status", "查看执行状态", "Get runtime status", RuntimeRiskLevel.READ, "project.read"),
    CapabilityDefinition(
        "retry_run",
        "重试运行",
        "Retry run",
        RuntimeRiskLevel.COSTING,
        "workflow.run",
        requires_approval_in_risky_only=True,
    ),
    CapabilityDefinition(
        "export_deliverable",
        "导出交付物",
        "Export deliverable",
        RuntimeRiskLevel.COSTING,
        "deliverables.export",
        requires_approval_in_risky_only=True,
    ),
    CapabilityDefinition(
        "generate_readiness_pack",
        "生成投标准备度包",
        "Generate bid readiness pack",
        RuntimeRiskLevel.LOW_RISK_WRITE,
        "deliverables.export",
        requires_approval_in_risky_only=True,
    ),
    CapabilityDefinition("semantic_search", "检索资料", "Search project evidence", RuntimeRiskLevel.READ, "project.read"),
    CapabilityDefinition(
        "web_search",
        "联网搜索",
        "Web search",
        RuntimeRiskLevel.READ,
    ),
    CapabilityDefinition(
        "fetch_url_to_project",
        "下载网页到项目",
        "Fetch URL into project",
        RuntimeRiskLevel.COSTING,
        "bundles.write",
        requires_approval_in_risky_only=True,
    ),
    CapabilityDefinition(
        "upload_document",
        "上传文档到项目",
        "Upload document to project",
        RuntimeRiskLevel.COSTING,
        "bundles.write",
        requires_approval_in_risky_only=True,
    ),
    CapabilityDefinition("search_bid_wiki", "查询 Bid Wiki", "Search Bid Wiki", RuntimeRiskLevel.READ, "memory.read"),
    CapabilityDefinition(
        "list_knowledge_portfolio",
        "查看知识资产概览",
        "View knowledge portfolio",
        RuntimeRiskLevel.READ,
    ),
    CapabilityDefinition(
        "propose_memory",
        "保存个人偏好",
        "Save personal preference",
        RuntimeRiskLevel.LOW_RISK_WRITE,
        requires_approval_in_risky_only=True,
    ),
    CapabilityDefinition(
        "forget_memory",
        "遗忘记忆",
        "Forget memory",
        RuntimeRiskLevel.DESTRUCTIVE,
        requires_approval_in_risky_only=True,
    ),
    CapabilityDefinition("open_page", "打开页面", "Open page", RuntimeRiskLevel.NAVIGATE),
    CapabilityDefinition(
        "delete_project",
        "删除项目",
        "Delete project",
        RuntimeRiskLevel.DESTRUCTIVE,
        "project.delete",
        requires_approval_in_risky_only=True,
        requires_typed_confirmation=True,
    ),
    CapabilityDefinition(
        "run_section_campaign",
        "多章节起草战役",
        "Run multi-section draft campaign",
        RuntimeRiskLevel.COSTING,
        "workflow.run",
        requires_approval_in_risky_only=True,
    ),
)

CAPABILITY_REGISTRY: dict[str, CapabilityDefinition] = {definition.name: definition for definition in _CAPABILITIES}
WORKFLOW_CAPABILITY_NAMES = frozenset(
    {
        "start_draft_section",
        "start_redraft_section",
        "resume_draft_run",
        "retry_run",
        "propose_memory_graph",
        "run_section_campaign",
    }
)


_REQUIRED_ARGUMENT_FIELDS: dict[str, tuple[str, ...]] = {
    "create_project": ("name",),
    "write_section": ("project_id", "section_key", "content_markdown"),
    "web_search": ("query",),
    "fetch_url_to_project": ("project_id", "url"),
    "semantic_search": ("project_id", "query"),
    "run_section_campaign": ("project_id",),
}


def missing_required_capability_arguments(capability_name: str, arguments: dict[str, Any]) -> tuple[str, ...]:
    """Return required action arguments that are absent or blank.

    This is a control-plane guard, not a prompt instruction: a model may plan a
    valid capability while omitting an argument, but it must never create an
    approval or reach a domain command with incomplete data.
    """
    missing: list[str] = []
    for field in _REQUIRED_ARGUMENT_FIELDS.get(capability_name, ()):
        value = arguments.get(field)
        if not isinstance(value, str) or not value.strip():
            missing.append(field)
    return tuple(missing)


def get_capability_definition(name: str) -> CapabilityDefinition:
    try:
        return CAPABILITY_REGISTRY[name]
    except KeyError as exc:
        raise ValueError(f"Unknown runtime capability: {name}") from exc


def is_workflow_capability(name: str) -> bool:
    return name in WORKFLOW_CAPABILITY_NAMES


def format_approval_request(capability_name: str, arguments: dict[str, Any]) -> str:
    """Return the one concise confirmation sentence shown to an end user."""
    if capability_name == "create_demo_workspace":
        return "确认创建内置演示工作区吗？它会占用一个项目名额，但不会使用 AI 额度。"
    if capability_name == "create_project":
        return f"确认创建项目「{arguments.get('name') or '未命名项目'}」吗？"
    if capability_name == "submit_review_decision":
        decision = "通过" if arguments.get("decision") == "approved" else "退回"
        return f"确认提交章节审核决定：{decision}吗？"
    if capability_name == "create_deliverable":
        return f"确认创建交付物「{arguments.get('title') or '未命名交付物'}」吗？"
    if capability_name == "attach_uploaded_documents":
        count = len(arguments.get("attachment_ids") or [])
        return f"确认将 {count} 个附件加入项目资料包并开始解析吗？"
    if capability_name == "start_draft_section":
        return f"确认启动章节「{arguments.get('section_key') or '未指定章节'}」的起草工作流吗？"
    if capability_name == "write_section":
        return f"确认把内容写入章节「{arguments.get('section_key') or '未指定章节'}」吗？"
    if capability_name == "run_section_campaign":
        mode = arguments.get("mode") or "framework"
        max_sections = arguments.get("max_sections") or 3
        if mode == "plan":
            return "确认生成多章节战役计划（只规划不写入）吗？"
        return (
            f"确认启动多章节战役吗？模式={mode}，每波最多处理 {max_sections} 章。"
            "会写入章节骨架或启动起草工作流，并可能分多波继续。"
        )
    if capability_name == "start_redraft_section":
        return f"确认启动章节「{arguments.get('section_key') or '未指定章节'}」的重写工作流吗？"
    if capability_name == "resume_draft_run":
        decision = "通过" if arguments.get("decision") == "approved" else "退回并继续修改"
        return f"确认对章节草稿提交审核决定：{decision}吗？"
    if capability_name == "propose_memory_graph":
        return "确认从这条已验证的项目知识生成实体关系提案吗？该操作会使用一次模型额度，结果仍需人工审核。"
    if capability_name == "retry_run":
        return "确认重新启动这次工作流吗？"
    if capability_name == "export_deliverable":
        return f"确认导出 {str(arguments.get('format') or 'docx').upper()} 文件吗？"
    if capability_name == "fetch_url_to_project":
        url = arguments.get("url")
        if isinstance(url, str) and url.strip():
            return f"确认把网页资源下载到项目吗？\n{url.strip()[:120]}"
        return "确认把网页资源下载到当前项目资料包吗？"
    if capability_name == "upload_document":
        return "确认把文件上传/入库到当前项目资料包吗？"
    if capability_name == "generate_readiness_pack":
        return "确认生成当前项目的投标准备度包吗？"
    if capability_name == "propose_memory":
        return "确认保存这条个人工作偏好吗？"
    if capability_name == "forget_memory":
        return "确认遗忘这条记忆吗？它将不再进入后续 Agent 上下文。"
    if capability_name == "delete_project":
        name = arguments.get("project_name") or arguments.get("name")
        if isinstance(name, str) and name.strip():
            return f"删除项目「{name.strip()}」后无法恢复。请输入完整项目名称确认继续。"
        return "删除项目后无法恢复。请输入完整项目名称确认继续。"
    return "该操作会改变平台数据。确认继续吗？"


def format_public_result(capability_name: str, result: dict[str, Any]) -> PublicCapabilityResult:
    """Format a bounded, user-facing summary without exposing implementation names."""
    count = _result_count(result)
    if capability_name == "search_projects":
        projects = _public_items(
            result.get("items") or result.get("projects"),
            ("id", "short_id", "name", "status", "created_at", "name_collision", "scenario_package"),
        )
        payload: dict[str, Any] = {"count": count}
        if projects:
            payload["projects"] = projects
        if any(item.get("name_collision") for item in projects):
            lines = [
                f"- {item.get('name')} · id={item.get('short_id') or str(item.get('id') or '')[:8]}"
                + (
                    f" · 创建于 {str(item.get('created_at'))[:10]}"
                    if item.get("created_at")
                    else ""
                )
                for item in projects
                if isinstance(item, dict)
            ]
            summary = f"找到 {count} 个项目（存在同名，请用 id/short_id 区分，不要编造 (1)/(2) 标签）：\n" + "\n".join(lines)
        else:
            summary = f"找到 {count} 个项目。"
        return PublicCapabilityResult(summary, payload)
    if capability_name == "create_demo_workspace" and isinstance(result.get("name"), str):
        summary = (
            f"演示工作区「{result['name']}」已准备好。"
            if result.get("created") is not False
            else f"已打开现有演示工作区「{result['name']}」。"
        )
        return PublicCapabilityResult(
            summary,
            {key: result[key] for key in ("id", "name", "status", "created") if key in result},
        )
    if capability_name == "create_project" and isinstance(result.get("name"), str):
        return PublicCapabilityResult(
            f"项目「{result['name']}」已创建。",
            {key: result[key] for key in ("id", "name", "status") if key in result},
        )
    if capability_name == "submit_review_decision" and isinstance(result.get("decision"), str):
        summary = "章节审核已通过。" if result["decision"] == "approved" else "章节已退回修改。"
        return PublicCapabilityResult(
            summary,
            {key: result[key] for key in ("section_id", "decision", "review_thread_id") if key in result},
        )
    if capability_name == "get_project_summary" and isinstance(result.get("name"), str):
        return PublicCapabilityResult(
            f"项目「{result['name']}」当前状态是 {result.get('status') or '未知'}。",
            {key: result[key] for key in ("id", "name", "status", "scenario_package") if key in result},
        )
    if capability_name == "create_deliverable" and isinstance(result.get("title"), str):
        return PublicCapabilityResult(
            f"交付物「{result['title']}」已创建。",
            {key: result[key] for key in ("id", "title", "status") if key in result},
        )
    if capability_name == "attach_uploaded_documents":
        count = result.get("attachment_count")
        if isinstance(count, int):
            payload = {
                key: result[key]
                for key in ("bundle_id", "bundle_label", "attachment_count", "ingest_queued")
                if key in result
            }
            summary = (
                f"已将 {count} 个附件加入资料包，并开始解析。"
                if result.get("ingest_queued") is not False
                else f"已将 {count} 个附件加入资料包；解析任务等待重新提交。"
            )
            return PublicCapabilityResult(summary, payload)
    if capability_name == "list_requirements":
        return PublicCapabilityResult(f"找到 {count} 条需求。", {"count": count})
    if capability_name == "list_claim_review_queue":
        ready_count = result.get("ready_to_verify_count")
        blocked_count = result.get("blocked_by_evidence_count")
        payload = {"count": count}
        if isinstance(ready_count, int):
            payload["ready_to_verify_count"] = ready_count
        if isinstance(blocked_count, int):
            payload["blocked_by_evidence_count"] = blocked_count
        return PublicCapabilityResult(
            (
                f"有 {count} 条 AI 主张等待人工核验，"
                f"其中 {ready_count if isinstance(ready_count, int) else 0} 条已具备核验条件。"
            ),
            payload,
        )
    if capability_name == "search_bid_wiki":
        return PublicCapabilityResult(f"找到 {count} 条可用记忆。", {"count": count})
    if capability_name == "list_knowledge_portfolio":
        projects = _public_items(
            result.get("items"),
            (
                "project_id",
                "project_name",
                "active_shared_count",
                "proposed_shared_count",
                "latest_compilation_status",
            ),
        )
        payload: dict[str, Any] = {"count": count}
        if projects:
            payload["projects"] = projects
        return PublicCapabilityResult(f"已检查 {count} 个可访问项目的知识状态。", payload)
    if capability_name == "propose_memory" and isinstance(result.get("id"), str):
        return PublicCapabilityResult("已保存为个人工作偏好。", {"memory_id": result["id"]})
    if capability_name == "forget_memory" and result.get("deleted") is True:
        return PublicCapabilityResult("这条记忆已遗忘。", {"deleted": True})
    if capability_name == "list_sections":
        # Keep section_key/title so the harness can chain into start_draft_section.
        sections = _public_items(
            result.get("items"),
            (
                "section_key",
                "title",
                "status",
                "has_content",
                "deliverable_id",
                "id",
            ),
        )
        payload: dict[str, Any] = {"count": count}
        if sections:
            payload["sections"] = sections
        drafted = result.get("drafted_count")
        approved = result.get("approved_count")
        if isinstance(drafted, int):
            payload["drafted_count"] = drafted
        if isinstance(approved, int):
            payload["approved_count"] = approved
        return PublicCapabilityResult(
            f"已找到 {count} 个章节。",
            payload,
        )
    if capability_name == "get_project_outline":
        drafted = result.get("drafted_count")
        approved = result.get("approved_count")
        # Outline-first drafting needs concrete section_key values in the LLM track.
        sections = _public_items(
            result.get("items"),
            (
                "section_key",
                "title",
                "status",
                "has_content",
                "in_template",
                "deliverable_id",
                "id",
            ),
        )
        payload = {"count": count}
        if isinstance(drafted, int):
            payload["drafted_count"] = drafted
        if isinstance(approved, int):
            payload["approved_count"] = approved
        if isinstance(result.get("project_id"), str):
            payload["project_id"] = result["project_id"]
        if isinstance(result.get("project_name"), str):
            payload["project_name"] = result["project_name"]
        if sections:
            payload["sections"] = sections
        return PublicCapabilityResult(
            f"大纲共 {count} 章，已起草 {drafted if isinstance(drafted, int) else 0} 章，"
            f"已批准 {approved if isinstance(approved, int) else 0} 章。",
            payload,
        )
    if capability_name == "list_deliverables":
        deliverables = _public_items(
            result.get("items"),
            ("id", "title", "status", "type"),
        )
        payload = {"count": count}
        if deliverables:
            payload["deliverables"] = deliverables
        return PublicCapabilityResult(f"已找到 {count} 条相关记录。", payload)
    if capability_name in {
        "list_project_bundles",
        "list_pending_reviews",
        "list_evidence",
        "list_documents",
        "get_section_versions",
        "get_runtime_status",
    }:
        return PublicCapabilityResult(f"已找到 {count} 条相关记录。", {"count": count})
    if capability_name == "list_readiness_gaps":
        items = result.get("items")
        if isinstance(items, list):
            return PublicCapabilityResult(f"找到 {len(items)} 个待处理缺口。", {"count": len(items)})
    if capability_name == "get_readiness_summary":
        score = result.get("readiness_score")
        if isinstance(score, (int, float)):
            return PublicCapabilityResult(f"当前投标准备度为 {score:.1f} 分。", {"readiness_score": score})
    if capability_name == "open_page":
        route = result.get("route")
        return PublicCapabilityResult("已准备好跳转页面。", {"route": route} if isinstance(route, str) else {})
    if capability_name in {"start_draft_section", "start_redraft_section"}:
        payload = {
            key: result[key]
            for key in ("run_id", "runtime_run_id")
            if isinstance(result.get(key), str)
        }
        summary = "起草工作流已启动。" if capability_name == "start_draft_section" else "重写工作流已启动。"
        return PublicCapabilityResult(summary, payload)
    if capability_name == "write_section":
        payload = {
            key: result[key]
            for key in (
                "section_id",
                "section_key",
                "section_title",
                "section_version_id",
                "version_number",
                "deliverable_id",
            )
            if key in result
        }
        title = result.get("section_title") or result.get("section_key") or "章节"
        return PublicCapabilityResult(f"已写入章节「{title}」。", payload)
    if capability_name == "run_section_campaign":
        payload = {
            key: result[key]
            for key in (
                "project_id",
                "mode",
                "processed_count",
                "remaining_count",
                "processed_section_keys",
                "remaining_section_keys",
                "planned_sections",
                "started_runtime_run_ids",
                "written_section_keys",
                "failed",
                "has_more",
                "waves_run",
                "auto_continue",
            )
            if key in result
        }
        processed = result.get("processed_count") or 0
        remaining = result.get("remaining_count") or 0
        waves = result.get("waves_run") or 0
        mode = result.get("mode") or "framework"
        if mode == "plan":
            summary = f"多章节战役规划完成：待处理 {remaining} 章。"
        else:
            summary = f"多章节战役（{mode}）完成 {waves} 波、处理 {processed} 章"
            if remaining:
                summary += f"，剩余 {remaining} 章待下一波"
            summary += "。"
        return PublicCapabilityResult(summary, payload)
    if capability_name == "semantic_search":
        items = _public_items(
            result.get("items"),
            ("chunk_id", "source_document_id", "score", "excerpt", "heading", "page"),
        )
        payload = {"count": count}
        if items:
            payload["items"] = items
        return PublicCapabilityResult(f"检索到 {count} 条相关资料片段。", payload)
    if capability_name == "web_search":
        items = _public_items(result.get("items"), ("title", "url", "snippet"))
        payload = {"count": count, "provider": result.get("provider"), "query": result.get("query")}
        if items:
            payload["items"] = items
        return PublicCapabilityResult(
            f"联网搜索返回 {count} 条结果。",
            {k: v for k, v in payload.items() if v is not None},
        )
    if capability_name in {"fetch_url_to_project", "upload_document"}:
        payload = {
            key: result[key]
            for key in (
                "project_id",
                "bundle_id",
                "document_id",
                "filename",
                "bytes",
                "source_url",
                "parse_status",
                "attachment_count",
                "ingest_queued",
            )
            if key in result
        }
        if capability_name == "fetch_url_to_project":
            name = result.get("filename") or "资源"
            return PublicCapabilityResult(f"已下载「{name}」到项目。", payload)
        name = result.get("filename") or "文档"
        if "attachment_count" in result:
            return PublicCapabilityResult(
                f"已将 {result.get('attachment_count')} 个附件加入资料包。",
                payload,
            )
        return PublicCapabilityResult(f"已上传「{name}」到项目。", payload)
    if capability_name == "resume_draft_run":
        payload = {
            key: result[key]
            for key in ("run_id", "runtime_run_id", "status")
            if key in result
        }
        return PublicCapabilityResult("已提交章节审核决定，工作流继续执行。", payload)
    if capability_name == "propose_memory_graph" and isinstance(result.get("run_id"), str):
        payload = {
            key: result[key]
            for key in ("run_id", "runtime_run_id", "reused")
            if key in result
        }
        summary = "已复用正在处理的实体关系提案。" if result.get("reused") else "实体关系提案已启动。"
        return PublicCapabilityResult(summary, payload)
    if capability_name == "retry_run" and isinstance(result.get("id"), str):
        payload = {"run_id": result["id"]}
        if isinstance(result.get("runtime_run_id"), str):
            payload["runtime_run_id"] = result["runtime_run_id"]
        return PublicCapabilityResult("已创建新的工作流尝试。", payload)
    if capability_name == "export_deliverable" and result.get("status") == "ready":
        payload = {
            key: result[key]
            for key in ("format", "download_path", "persisted")
            if key in result
        }
        return PublicCapabilityResult("交付物导出已就绪。", payload)
    if capability_name == "generate_readiness_pack" and isinstance(result.get("pack_id"), str):
        payload = {
            key: result[key]
            for key in ("pack_id", "version_number", "xlsx_download_path", "docx_download_path")
            if key in result
        }
        return PublicCapabilityResult("投标准备度包已生成。", payload)
    if capability_name == "delete_project" and result.get("deleted") is True:
        return PublicCapabilityResult("项目已删除。", {"deleted": True})
    return PublicCapabilityResult("操作已完成。", {})


def _result_count(result: dict[str, Any]) -> int:
    count = result.get("count")
    if isinstance(count, int) and count >= 0:
        return count
    items = result.get("items")
    if isinstance(items, list):
        return len(items)
    for key in ("projects", "requirements", "bundles", "sections", "runs", "versions"):
        value = result.get(key)
        if isinstance(value, list):
            return len(value)
    return 0


def _public_items(
    value: Any,
    allowed_keys: tuple[str, ...],
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [
        {key: item[key] for key in allowed_keys if key in item}
        for item in value[:limit]
        if isinstance(item, dict)
    ]
