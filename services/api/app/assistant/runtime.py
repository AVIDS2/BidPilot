"""Assistant intent runtime.

The first production slice keeps platform mutation deterministic and bounded.
OpenAI Agents SDK is wired as the model-mediated harness path, but it is only
used when explicitly enabled so tests and local development never call a model
by accident.
"""

from __future__ import annotations

import os
import re

from .schemas import AssistantIntent

try:  # pragma: no cover - import availability depends on optional dependency sync.
    from agents import Agent, Runner
except Exception:  # pragma: no cover
    Agent = None  # type: ignore[assignment]
    Runner = None  # type: ignore[assignment]


_ASSISTANT_INSTRUCTIONS = """
你是 BidPilot 平台的执行型助手，只负责把用户请求路由成结构化意图。

行为边界：
- 只输出 AssistantIntent，不输出普通聊天文本之外的解释。
- 不要反复复述“我能做什么”的能力清单；优先推进当前任务。
- 如果上一轮已经在等待某个字段，用户的短回复如“你来”“开始吧”“都行”“默认”表示授权你使用合理默认值继续。
- 平台动作必须通过工具层执行，不能直接声称已经创建、起草、重写或修改成功。
- 创建、起草、重写等变更类动作需要确认；确认前只返回 confirmation 请求所需的结构化意图。
- 生成实体关系提案只能针对当前项目中已有证据的共享知识记录；缺少来源记录 ID 时只请求该 ID，不能猜测来源。
- 信息不足时只问一个最关键的缺失字段。
"""


class AssistantRuntime:
    async def classify(self, message: str, project_id: str | None = None) -> AssistantIntent:
        if self._sdk_enabled():
            sdk_intent = await self._classify_with_openai_agents(message, project_id)
            if sdk_intent is not None:
                return sdk_intent
        return classify_locally(message, project_id)

    def _sdk_enabled(self) -> bool:
        return (
            os.getenv("DOCPILOT_ASSISTANT_USE_OPENAI_AGENTS", "false").lower() == "true"
            and bool(os.getenv("OPENAI_API_KEY"))
            and Agent is not None
            and Runner is not None
        )

    async def _classify_with_openai_agents(
        self,
        message: str,
        project_id: str | None,
    ) -> AssistantIntent | None:
        if Agent is None or Runner is None:
            return None

        agent = Agent(
            name="BidPilot Assistant Intent Router",
            instructions=_ASSISTANT_INSTRUCTIONS,
            output_type=AssistantIntent,
        )
        prompt = f"当前 project_id: {project_id or '无'}\n用户消息: {message}"
        result = await Runner.run(agent, prompt)
        output = getattr(result, "final_output", None)
        if isinstance(output, AssistantIntent):
            return output
        if isinstance(output, dict):
            return AssistantIntent.model_validate(output)
        return None


def classify_locally(message: str, project_id: str | None = None) -> AssistantIntent:
    text = message.strip()
    lowered = text.lower()

    if _looks_like_demo_workspace(text):
        return AssistantIntent(
            mode="tool_action",
            tool_name="create_demo_workspace",
            arguments={},
        )

    if _looks_like_create_project(text):
        name = _extract_project_name(text)
        if not name:
            return AssistantIntent(
                mode="needs_input",
                tool_name="create_project",
                missing_fields=["name"],
                response="要创建项目的话，我还需要项目名称。",
            )
        return AssistantIntent(
            mode="tool_action",
            tool_name="create_project",
            arguments={"name": name, "scenario_package": "bidpilot"},
        )

    if _looks_like_delete_project(text):
        return _project_scoped_intent(
            tool_name="delete_project",
            project_id=project_id,
            action_label="删除项目",
        )

    if _looks_like_memory_graph_extraction(text):
        return _memory_graph_extraction_intent(text, project_id)

    if _looks_like_draft(text):
        if not project_id:
            return AssistantIntent(
                mode="needs_input",
                tool_name="start_draft_section",
                missing_fields=["project_id"],
                response="我可以帮你起草章节，但需要先知道要操作哪个项目。",
            )
        return AssistantIntent(
            mode="workflow_trigger",
            tool_name="start_draft_section",
            arguments={
                "project_id": project_id,
                "section_key": _extract_section_key(text),
            },
        )

    if _looks_like_open_page(text):
        return AssistantIntent(
            mode="tool_action",
            tool_name="open_page",
            arguments={"route": _route_for_message(lowered)},
        )

    if _looks_like_readiness_gap(text):
        return _project_scoped_intent(
            tool_name="list_readiness_gaps",
            project_id=project_id,
            arguments={"kind": _readiness_gap_kind(text)},
            action_label="查看项目就绪缺口",
        )

    if _looks_like_claim_review_queue(text):
        return _project_scoped_intent(
            tool_name="list_claim_review_queue",
            project_id=project_id,
            action_label="查看待核验主张",
        )

    if _looks_like_forget_memory(text):
        memory_id = _extract_memory_id(text)
        if not memory_id:
            return AssistantIntent(
                mode="needs_input",
                tool_name="forget_memory",
                missing_fields=["memory_id"],
                response="我需要知道要遗忘哪一条记忆。请在 Bid Wiki 中复制记忆 ID 后发送给我。",
            )
        return AssistantIntent(
            mode="tool_action",
            tool_name="forget_memory",
            arguments={"memory_id": memory_id},
        )

    if _looks_like_remember(text):
        body = _extract_memory_body(text)
        if not body:
            return AssistantIntent(
                mode="needs_input",
                tool_name="propose_memory",
                missing_fields=["body_markdown"],
                response="请告诉我需要记住的具体偏好或工作约定。",
            )
        return AssistantIntent(
            mode="tool_action",
            tool_name="propose_memory",
            arguments={
                "scope": "user_private",
                "kind": "preference",
                "title": "个人工作偏好",
                "body_markdown": body,
            },
        )

    if _looks_like_knowledge_portfolio(text):
        return AssistantIntent(
            mode="tool_action",
            tool_name="list_knowledge_portfolio",
            arguments={},
        )

    if _looks_like_bid_wiki_search(text):
        return _project_scoped_intent(
            tool_name="search_bid_wiki",
            project_id=project_id,
            arguments={"query": text},
            action_label="查看项目 Bid Wiki",
        )

    if _looks_like_generate_readiness_pack(text):
        return _project_scoped_intent(
            tool_name="generate_readiness_pack",
            project_id=project_id,
            action_label="生成投标准备度包",
        )

    if _looks_like_readiness(text):
        return _project_scoped_intent(
            tool_name="get_readiness_summary",
            project_id=project_id,
            action_label="查看项目就绪度",
        )

    if _looks_like_requirement_source(text):
        requirement_id = _extract_requirement_id(text)
        if not requirement_id:
            return AssistantIntent(
                mode="needs_input",
                tool_name="open_requirement_source",
                missing_fields=["requirement_id"],
                response="我需要先知道要定位哪一条需求的来源。请在需求详情中复制需求 ID 后发送给我。",
            )
        return AssistantIntent(
            mode="tool_action",
            tool_name="open_requirement_source",
            arguments={"requirement_id": requirement_id},
        )

    if _looks_like_review_decision(text):
        section_id = _extract_requirement_id(text)
        if not project_id:
            return AssistantIntent(
                mode="needs_input",
                tool_name="submit_review_decision",
                missing_fields=["project_id"],
                response="提交审核决定前，我需要先知道要操作哪个项目。",
            )
        if not section_id:
            return AssistantIntent(
                mode="needs_input",
                tool_name="submit_review_decision",
                missing_fields=["section_id"],
                response="请提供要审核的章节 ID，或先让我列出待审核章节。",
            )
        decision = "approved" if any(word in text.lower() for word in ("通过", "批准", "approve")) else "rejected"
        return AssistantIntent(
            mode="tool_action",
            tool_name="submit_review_decision",
            arguments={"project_id": project_id, "section_id": section_id, "decision": decision},
        )

    if "项目" in text and any(word in text for word in ("找", "搜索", "查询", "列出", "看看")):
        return AssistantIntent(
            mode="tool_action",
            tool_name="search_projects",
            arguments={"query": _extract_search_query(text)},
        )

    if _looks_like_list_requirements(text):
        return _project_scoped_intent(
            tool_name="list_requirements",
            project_id=project_id,
            action_label="查看项目需求",
        )

    if _looks_like_list_evidence(text):
        return _project_scoped_intent(
            tool_name="list_evidence",
            project_id=project_id,
            action_label="查看项目证据",
        )

    if _looks_like_list_documents(text):
        return _project_scoped_intent(
            tool_name="list_documents",
            project_id=project_id,
            action_label="查看项目文档",
        )

    if _looks_like_list_versions(text):
        return _project_scoped_intent(
            tool_name="get_section_versions",
            project_id=project_id,
            action_label="查看章节版本",
        )

    if _looks_like_export(text):
        deliverable_id = _extract_deliverable_id(text)
        if not deliverable_id:
            return AssistantIntent(
                mode="needs_input",
                tool_name="export_deliverable",
                missing_fields=["deliverable_id"],
                response="我需要知道要导出哪个交付物。请在交付物详情中复制交付物 ID 后发送给我。",
            )
        return AssistantIntent(
            mode="tool_action",
            tool_name="export_deliverable",
            arguments={
                "deliverable_id": deliverable_id,
                "format": "pdf" if "pdf" in lowered else "docx",
            },
        )

    return AssistantIntent(
        mode="answer",
        response="我没抓到一个明确的平台动作。你可以直接说“创建项目：项目名”或“打开项目页面”，我会继续执行到确认步骤。",
    )


def _looks_like_create_project(text: str) -> bool:
    return "项目" in text and any(word in text for word in ("创建", "新建", "建一个", "开一个"))


def _looks_like_delete_project(text: str) -> bool:
    lowered = text.lower()
    return "项目" in text and any(token in lowered for token in ("删除", "移除", "delete", "remove"))


def _looks_like_demo_workspace(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ("演示工作区", "演示项目", "demo workspace", "demo project")) or (
        any(token in lowered for token in ("体验", "试用", "看看"))
        and any(token in lowered for token in ("演示", "demo", "示例"))
    )


def _looks_like_draft(text: str) -> bool:
    return any(word in text for word in ("起草", "撰写", "生成", "草稿", "draft")) and any(
        word in text for word in ("章节", "方案", "section", "技术")
    )


def _looks_like_open_page(text: str) -> bool:
    return any(word in text for word in ("打开", "进入", "跳转", "去")) and any(
        word in text for word in ("页面", "项目", "文档", "价格", "设置", "供应商", "仪表盘", "知识", "wiki")
    )


def _extract_project_name(text: str) -> str | None:
    patterns = [
        r"(?:名字叫|名称叫|名为|叫|为)\s*([^,，。.!！?？]+)",
        r"项目\s*([^,，。.!！?？]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(1).strip("“”\"' ")
            if name and name not in {"项目", "名字", "名称"}:
                return name[:80]
    return None


def _extract_section_key(text: str) -> str:
    if "执行" in text or "实施" in text:
        return "implementation-plan"
    if "商务" in text:
        return "commercial-response"
    if "摘要" in text or "概述" in text:
        return "executive-summary"
    return "technical-approach"


def _route_for_message(lowered: str) -> str:
    if "价格" in lowered or "pricing" in lowered:
        return "/pricing"
    if "文档" in lowered or "docs" in lowered:
        return "/docs"
    if "设置" in lowered or "供应商" in lowered or "provider" in lowered:
        return "/settings/providers"
    if "仪表盘" in lowered or "dashboard" in lowered:
        return "/"
    if "知识" in lowered or "wiki" in lowered:
        return "/knowledge"
    return "/projects"


def _extract_search_query(text: str) -> str | None:
    query = re.sub(r"(找|搜索|查询|列出|看看|项目)", "", text).strip()
    return query or None


def _project_scoped_intent(
    *,
    tool_name: str,
    project_id: str | None,
    action_label: str,
    arguments: dict[str, str] | None = None,
) -> AssistantIntent:
    if not project_id:
        return AssistantIntent(
            mode="needs_input",
            tool_name=tool_name,
            missing_fields=["project_id"],
            response=f"要{action_label}，我需要先知道要操作哪个项目。请先打开项目工作台，或告诉我项目名称。",
        )
    return AssistantIntent(
        mode="tool_action",
        tool_name=tool_name,
        arguments={"project_id": project_id, **(arguments or {})},
    )


def _looks_like_remember(text: str) -> bool:
    return any(token in text.lower() for token in ("记住", "记下", "remember", "保存偏好"))


def _looks_like_forget_memory(text: str) -> bool:
    return any(token in text.lower() for token in ("遗忘", "忘记这条", "删除记忆", "forget memory"))


def _looks_like_bid_wiki_search(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ("bid wiki", "知识库", "知识图谱", "项目记忆")) and any(
        token in lowered for token in ("查看", "搜索", "查询", "看看", "什么", "有哪些", "search", "show")
    )


def _looks_like_memory_graph_extraction(text: str) -> bool:
    lowered = text.lower()
    requests_generation = any(token in lowered for token in ("生成", "提取", "构建", "创建", "generate", "extract", "build"))
    mentions_graph = any(token in lowered for token in ("实体关系", "实体", "关系提案", "知识图谱", "entity relation", "knowledge graph"))
    return requests_generation and mentions_graph


def _memory_graph_extraction_intent(text: str, project_id: str | None) -> AssistantIntent:
    if not project_id:
        return AssistantIntent(
            mode="needs_input",
            tool_name="propose_memory_graph",
            missing_fields=["project_id"],
            response="要生成实体关系提案，我需要先知道要操作哪个项目。请先打开项目工作台，或告诉我项目名称。",
        )
    memory_record_id = _extract_memory_id(text)
    if not memory_record_id:
        return AssistantIntent(
            mode="needs_input",
            tool_name="propose_memory_graph",
            arguments={"project_id": project_id},
            missing_fields=["memory_record_id"],
            response="请提供要分析的共享知识记录 ID。你可以在项目 Bid Wiki 中选择一条带来源的已激活记录后复制它的 ID。",
        )
    return AssistantIntent(
        mode="workflow_trigger",
        tool_name="propose_memory_graph",
        arguments={"project_id": project_id, "memory_record_id": memory_record_id},
    )


def _looks_like_knowledge_portfolio(text: str) -> bool:
    """Recognize cross-project discovery without turning it into global RAG."""
    lowered = text.lower()
    mentions_knowledge = any(
        token in lowered
        for token in ("知识资产", "知识健康", "知识审核", "知识库概览", "bid wiki", "wiki 审核")
    )
    asks_across_projects = any(
        token in lowered
        for token in ("哪些项目", "所有项目", "项目列表", "项目概览", "待审核项目", "需要审核")
    )
    return mentions_knowledge and asks_across_projects


def _extract_memory_body(text: str) -> str | None:
    value = re.sub(r"^.*?(?:记住|记下|remember|保存偏好)\s*[:：，,]?\s*", "", text, flags=re.IGNORECASE).strip()
    return value[:1000] or None


def _extract_memory_id(text: str) -> str | None:
    match = re.search(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        text,
    )
    return match.group(0) if match else None


def _looks_like_readiness(text: str) -> bool:
    return any(word in text for word in ("就绪度", "准备度", "准备情况", "readiness"))


def _looks_like_generate_readiness_pack(text: str) -> bool:
    return any(word in text for word in ("生成", "导出", "下载", "generate", "export")) and any(
        word in text for word in ("就绪", "准备度", "准备包", "readiness")
    )


def _looks_like_readiness_gap(text: str) -> bool:
    return any(word in text for word in ("缺口", "风险项", "高风险", "未覆盖", "矛盾项", "逾期")) and any(
        word in text for word in ("查看", "列出", "看看", "有哪些", "多少", "list", "show")
    )


def _looks_like_claim_review_queue(text: str) -> bool:
    lowered = text.lower()
    mentions_claim = any(token in lowered for token in ("主张", "claim", "claims"))
    asks_for_review = any(
        token in lowered
        for token in (
            "待核验",
            "待验证",
            "待审核",
            "核验",
            "核查",
            "验证",
            "claim review",
            "claims waiting",
        )
    )
    return mentions_claim and asks_for_review


def _readiness_gap_kind(text: str) -> str:
    lowered = text.lower()
    if "高风险" in text or "high risk" in lowered:
        return "high_risk"
    if "强制" in text or "mandatory" in lowered:
        return "mandatory"
    if "证据" in text or "evidence" in lowered:
        return "evidence"
    if "矛盾" in text or "contradiction" in lowered:
        return "contradictions"
    if "逾期" in text or "overdue" in lowered:
        return "overdue"
    if "未覆盖" in text or "uncovered" in lowered:
        return "uncovered"
    return "all"


def _looks_like_requirement_source(text: str) -> bool:
    return "需求" in text and any(word in text for word in ("来源", "定位", "原文", "出处", "source", "locator"))


def _looks_like_review_decision(text: str) -> bool:
    lowered = text.lower()
    return any(word in text for word in ("审核", "审批", "评审")) and any(
        word in lowered for word in ("通过", "批准", "退回", "驳回", "approve", "reject")
    )


def _extract_requirement_id(text: str) -> str | None:
    match = re.search(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        text,
    )
    return match.group(0) if match else None


def _extract_deliverable_id(text: str) -> str | None:
    return _extract_requirement_id(text)


def _looks_like_list_requirements(text: str) -> bool:
    return any(word in text for word in ("需求", "要求", "requirement")) and any(
        word in text for word in ("查看", "列出", "看看", "有哪些", "多少", "list", "show")
    )


def _looks_like_list_evidence(text: str) -> bool:
    return any(word in text for word in ("证据", "知识", "引用", "evidence", "chunk")) and any(
        word in text for word in ("查看", "列出", "看看", "有哪些", "多少", "list", "show")
    )


def _looks_like_list_documents(text: str) -> bool:
    return any(word in text for word in ("文档", "资料", "文件", "document")) and any(
        word in text for word in ("查看", "列出", "看看", "有哪些", "多少", "list", "show")
    )


def _looks_like_list_versions(text: str) -> bool:
    return any(word in text for word in ("版本", "历史", "version", "history")) and any(
        word in text for word in ("查看", "列出", "看看", "有哪些", "list", "show")
    )


def _looks_like_export(text: str) -> bool:
    return any(word in text for word in ("导出", "下载", "export", "download", "docx", "pdf"))
