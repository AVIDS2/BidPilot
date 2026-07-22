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
        "start_redraft_section",
        "启动章节重写",
        "Start redraft section",
        RuntimeRiskLevel.COSTING,
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
)

CAPABILITY_REGISTRY: dict[str, CapabilityDefinition] = {definition.name: definition for definition in _CAPABILITIES}
WORKFLOW_CAPABILITY_NAMES = frozenset(
    {
        "start_draft_section",
        "start_redraft_section",
        "retry_run",
        "propose_memory_graph",
    }
)


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
    if capability_name == "start_redraft_section":
        return f"确认启动章节「{arguments.get('section_key') or '未指定章节'}」的重写工作流吗？"
    if capability_name == "propose_memory_graph":
        return "确认从这条已验证的项目知识生成实体关系提案吗？该操作会使用一次模型额度，结果仍需人工审核。"
    if capability_name == "retry_run":
        return "确认重新启动这次工作流吗？"
    if capability_name == "export_deliverable":
        return f"确认导出 {str(arguments.get('format') or 'docx').upper()} 文件吗？"
    if capability_name == "generate_readiness_pack":
        return "确认生成当前项目的投标准备度包吗？"
    if capability_name == "propose_memory":
        return "确认保存这条个人工作偏好吗？"
    if capability_name == "forget_memory":
        return "确认遗忘这条记忆吗？它将不再进入后续 Agent 上下文。"
    if capability_name == "delete_project":
        return "删除项目后无法恢复。请确认继续。"
    return "该操作会改变平台数据。确认继续吗？"


def format_public_result(capability_name: str, result: dict[str, Any]) -> PublicCapabilityResult:
    """Format a bounded, user-facing summary without exposing implementation names."""
    count = _result_count(result)
    if capability_name == "search_projects":
        projects = _public_items(result.get("items") or result.get("projects"), ("id", "name", "status"))
        payload: dict[str, Any] = {"count": count}
        if projects:
            payload["projects"] = projects
        return PublicCapabilityResult(f"找到 {count} 个项目。", payload)
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
    if capability_name in {
        "list_project_bundles",
        "list_sections",
        "list_pending_reviews",
        "list_evidence",
        "list_deliverables",
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
        return PublicCapabilityResult("起草工作流已启动。", payload)
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


def _public_items(value: Any, allowed_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [
        {key: item[key] for key in allowed_keys if key in item}
        for item in value[:10]
        if isinstance(item, dict)
    ]
