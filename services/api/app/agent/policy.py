"""Operator tool policy metadata for the BidPilot agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


RiskLevel = Literal["read", "navigate", "low_risk_write", "costing", "destructive"]
ApprovalMode = Literal["request_approval", "risky_only", "full_access", "custom"]


@dataclass(frozen=True)
class ToolPolicy:
    name: str
    label_zh: str
    label_en: str
    risk_level: RiskLevel
    requires_approval: bool = False
    requires_typed_confirmation: bool = False


TOOL_POLICIES: dict[str, ToolPolicy] = {
    "search_projects": ToolPolicy("search_projects", "搜索项目", "Search projects", "read"),
    "create_project": ToolPolicy("create_project", "创建项目", "Create project", "low_risk_write", True),
    "get_project_summary": ToolPolicy("get_project_summary", "查看项目概览", "Get project summary", "read"),
    "list_project_bundles": ToolPolicy("list_project_bundles", "查看资料包", "List project bundles", "read"),
    "list_sections": ToolPolicy("list_sections", "查看章节", "List sections", "read"),
    "list_pending_reviews": ToolPolicy("list_pending_reviews", "查看待审内容", "List pending reviews", "read"),
    "list_requirements": ToolPolicy("list_requirements", "查看需求", "List requirements", "read"),
    "list_evidence": ToolPolicy("list_evidence", "查看证据", "List evidence", "read"),
    "list_deliverables": ToolPolicy("list_deliverables", "查看交付物", "List deliverables", "read"),
    "list_documents": ToolPolicy("list_documents", "查看文档", "List documents", "read"),
    "get_section_versions": ToolPolicy("get_section_versions", "查看章节版本", "Get section versions", "read"),
    "create_deliverable": ToolPolicy("create_deliverable", "创建交付物", "Create deliverable", "low_risk_write", True),
    "start_draft_section": ToolPolicy("start_draft_section", "启动章节起草", "Start draft section", "costing", True),
    "start_redraft_section": ToolPolicy("start_redraft_section", "启动章节重写", "Start redraft section", "costing", True),
    "get_runtime_status": ToolPolicy("get_runtime_status", "查看执行状态", "Get runtime status", "read"),
    "retry_run": ToolPolicy("retry_run", "重试运行", "Retry run", "costing", True),
    "export_deliverable": ToolPolicy("export_deliverable", "导出交付物", "Export deliverable", "costing", True),
    "semantic_search": ToolPolicy("semantic_search", "语义搜索", "Semantic search", "read"),
    "open_page": ToolPolicy("open_page", "打开页面", "Open page", "navigate"),
    "delete_project": ToolPolicy(
        "delete_project",
        "删除项目",
        "Delete project",
        "destructive",
        True,
        True,
    ),
}


def get_tool_policy(tool_name: str) -> ToolPolicy | None:
    return TOOL_POLICIES.get(tool_name)


def tool_requires_approval(tool_name: str, approval_mode: ApprovalMode = "risky_only") -> bool:
    policy = get_tool_policy(tool_name)
    if policy is None:
        return True
    if policy.requires_typed_confirmation:
        return True
    if approval_mode == "full_access":
        return policy.risk_level == "destructive"
    if approval_mode in {"request_approval", "custom"}:
        return policy.risk_level not in {"read", "navigate"}
    return policy.requires_approval or policy.risk_level in {"costing", "destructive"}
