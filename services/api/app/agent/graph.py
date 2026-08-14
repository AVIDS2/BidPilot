"""Compatibility-only legacy ReAct graph.

The public Assistant route no longer imports or creates this graph; it is
retained temporarily for legacy checkpoint-policy coverage and must be deleted
after 2026-09-30 unless a documented migration dependency remains.
"""

from __future__ import annotations

import logging
import os
import threading

from langchain_core.messages import SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from sqlalchemy.orm import Session

from app.auth.schemas import CurrentUser
from app.memory.schemas import MemoryContextRead

from .llm import ReasoningEffort, get_agent_llm
from .tools import create_tools

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是 BidPilot 平台的 AI 助手。你帮助用户管理投标文档项目、上传资料、起草方案、审核和导出。

行为准则：
- 用中文回答，简洁专业
- 执行变更操作（创建项目、启动起草、删除等）前，先向用户确认
- 信息查询类操作直接执行，不需要确认
- 如果用户的需求不明确，只追问一个最关键的信息
- 工具执行失败时，告诉用户原因和建议的解决方案
- 可以混合对话和工具调用：先回答问题，再执行操作
- 如果用户用口语化表达，理解其意图并映射到正确的工具
- 当系统提供了暂存附件 ID 且用户要求将文件加入项目时，必须调用 attach_uploaded_documents；不要声称文件已入库，除非工具返回成功。
"""

_REASONING_GUIDANCE = {
    "low": "当前推理强度：低。优先快速、直接地完成任务，避免不必要的展开。",
    "medium": "当前推理强度：中。保持速度与准确性的平衡，检查关键前提后再行动。",
    "high": "当前推理强度：高。执行前更仔细地核对上下文、工具选择和潜在风险。",
    "extra": "当前推理强度：extra。先梳理目标、约束和可执行步骤，再谨慎调用工具。",
    "max": "当前推理强度：Max。以最高审慎度处理任务，完整核对上下文、边界、风险和最终输出。",
}


def _format_memory_context(memory_context: MemoryContextRead | None) -> str:
    if memory_context is None or not memory_context.items:
        return ""
    lines = [
        "\n已授权的长期记忆（仅作辅助；涉及事实时仍须检索原始资料并给出来源）：",
    ]
    for item in memory_context.items:
        sources = "；".join(citation.label for citation in item.citations[:3])
        lines.append(f"- [{item.scope.value}/{item.kind.value}] {item.title}: {item.body_markdown}\n  来源：{sources}")
    return "\n".join(lines)


def _build_system_prompt(
    reasoning_effort: str | None,
    memory_context: MemoryContextRead | None = None,
) -> str:
    guidance = _REASONING_GUIDANCE.get(reasoning_effort or "")
    prompt = _SYSTEM_PROMPT if not guidance else f"{_SYSTEM_PROMPT}\n{guidance}\n"
    return f"{prompt}{_format_memory_context(memory_context)}"

# ── Checkpointer singleton ────────────────────────────────────────────────────

_checkpointer = None
_checkpointer_cm = None
_lock = threading.Lock()


def _is_production_environment() -> bool:
    return os.environ.get("DOCPILOT_ENV", "local").lower() in {"production", "staging"}


def _checkpointer_mode() -> str:
    default_mode = "postgres" if _is_production_environment() else "memory"
    return os.environ.get(
        "DOCPILOT_AGENT_CHECKPOINTER",
        os.environ.get("DOCPILOT_LANGGRAPH_CHECKPOINTER", default_mode),
    ).lower()


def get_checkpointer():
    global _checkpointer, _checkpointer_cm
    if _checkpointer is not None:
        return _checkpointer

    with _lock:
        if _checkpointer is not None:
            return _checkpointer

        mode = _checkpointer_mode()
        if mode == "memory":
            if _is_production_environment():
                raise RuntimeError("DOCPILOT_AGENT_CHECKPOINTER must be postgres outside local development")
            _checkpointer = InMemorySaver()
            logger.info("Using explicit local InMemorySaver for agent checkpointer")
            return _checkpointer
        if mode != "postgres":
            raise RuntimeError(f"Unsupported DOCPILOT_AGENT_CHECKPOINTER mode: {mode}")

        database_url = os.environ.get(
            "DOCPILOT_DATABASE_URL",
            "postgresql+psycopg://docpilot:docpilot@localhost:5433/docpilot",
        )
        conn_str = database_url.replace("postgresql+psycopg://", "postgresql://", 1)

        try:
            from langgraph.checkpoint.postgres import PostgresSaver

            cm = PostgresSaver.from_conn_string(conn_str)
            checkpointer = cm.__enter__()
            _checkpointer = checkpointer
            _checkpointer_cm = cm
            logger.info("Using PostgresSaver for agent checkpointer")
        except Exception as exc:
            if "cm" in locals():
                cm.__exit__(None, None, None)
            raise RuntimeError(
                "PostgreSQL assistant checkpointer initialization failed. "
                "Run scripts/setup_langgraph_checkpoints.py during deployment before starting API or Worker."
            ) from exc

        return _checkpointer


def close_checkpointer():
    global _checkpointer, _checkpointer_cm
    if _checkpointer_cm is not None:
        try:
            _checkpointer_cm.__exit__(None, None, None)
        except Exception:
            pass
    _checkpointer = None
    _checkpointer_cm = None


# ── Agent builder ─────────────────────────────────────────────────────────────

def build_agent(
    db: Session,
    user: CurrentUser,
    provider_type: str = "openai",
    provider_id: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    provider_config_id: str | None = None,
    reasoning_effort: ReasoningEffort | None = None,
    approval_mode: str = "risky_only",
    memory_context: MemoryContextRead | None = None,
):
    """Build a ReAct agent with tools bound to the current db session and user."""
    llm = get_agent_llm(
        provider_type=provider_type,
        provider_id=provider_id,
        api_key=api_key,
        base_url=base_url,
        model=model,
        reasoning_effort=reasoning_effort,
    )
    tools = create_tools(
        db,
        user,
        provider_config_id=provider_config_id,
        reasoning_effort=reasoning_effort,
        approval_mode=approval_mode,  # type: ignore[arg-type]
    )
    checkpointer = get_checkpointer()

    agent = create_react_agent(
        llm,
        tools,
        prompt=SystemMessage(content=_build_system_prompt(reasoning_effort, memory_context)),
        checkpointer=checkpointer,
    )
    return agent
