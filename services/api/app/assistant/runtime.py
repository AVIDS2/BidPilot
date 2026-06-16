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

    if "项目" in text and any(word in text for word in ("找", "搜索", "查询", "列出", "看看")):
        return AssistantIntent(
            mode="tool_action",
            tool_name="search_projects",
            arguments={"query": _extract_search_query(text)},
        )

    return AssistantIntent(
        mode="answer",
        response="我没抓到一个明确的平台动作。你可以直接说“创建项目：项目名”或“打开项目页面”，我会继续执行到确认步骤。",
    )


def _looks_like_create_project(text: str) -> bool:
    return "项目" in text and any(word in text for word in ("创建", "新建", "建一个", "开一个"))


def _looks_like_draft(text: str) -> bool:
    return any(word in text for word in ("起草", "撰写", "生成", "草稿", "draft")) and any(
        word in text for word in ("章节", "方案", "section", "技术")
    )


def _looks_like_open_page(text: str) -> bool:
    return any(word in text for word in ("打开", "进入", "跳转", "去")) and any(
        word in text for word in ("页面", "项目", "文档", "价格", "设置", "供应商", "仪表盘")
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
    return "/projects"


def _extract_search_query(text: str) -> str | None:
    query = re.sub(r"(找|搜索|查询|列出|看看|项目)", "", text).strip()
    return query or None
