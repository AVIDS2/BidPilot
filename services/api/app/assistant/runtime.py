"""Model-backed assistant intent compatibility runtime.

The public assistant route uses the LangGraph operator planner. This module is
kept only for the retired compatibility service and deliberately has no local
or lexical intent classifier.
"""

from __future__ import annotations

import os
from typing import Any

from .schemas import AssistantIntent

Agent: Any
Runner: Any

try:  # pragma: no cover - optional dependency availability varies by install.
    from agents import Agent, Runner
except Exception:  # pragma: no cover
    Agent = None
    Runner = None


_ASSISTANT_INSTRUCTIONS = """
你是 BidPilot 平台的执行型助手，只输出结构化 AssistantIntent。

平台动作必须通过工具层执行，不能虚构执行结果。变更类动作需要确认；信息不足时只
要求最关键的字段。必须根据完整的自然语言上下文理解用户意图，不使用关键词匹配或
本地规则猜测意图。
"""


class AssistantRuntime:
    async def classify(self, message: str, project_id: str | None = None) -> AssistantIntent:
        if not self._sdk_enabled():
            raise RuntimeError(
                "Assistant model runtime is unavailable; refusing lexical intent fallback."
            )
        result = await self._classify_with_openai_agents(message, project_id)
        if result is None:
            raise RuntimeError("Assistant model did not return a valid structured intent.")
        return result

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
