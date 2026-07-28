"""Streaming tool-calling harness for the governed assistant.

This is intentionally thin: native model tool calls + execute_capability +
live SSE. It replaces the batch structured-plan operator path as the product
assistant loop while keeping authorization, approval, audit, and quotas.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from sqlalchemy.orm import Session

from app.assistant.audit import redact_arguments, redact_text
from app.assistant.task_state import clear_task_state, set_task_state
from app.auth.schemas import CurrentUser
from app.chat.service import bind_conversation_project_context, save_message
from app.models import RuntimeRun
from app.usage.schemas import ProviderSource
from app.usage.service import UsageLimitExceeded, reserve_assistant_model_tokens
from contracts.model_usage import ProviderUsageMeasurement, normalize_langchain_usage
from contracts.usage_ledger import (
    mark_model_reservation_uncertain,
    record_model_usage,
    release_model_reservation,
    settle_model_reservation,
)

from .background_tasks import collect_completed_notifications
from .failures import PublicRuntimeFailure, classify_capability_failure
from .hooks import HookContext, default_hook_registry, register_default_recovery_hooks
from .registry import (
    CAPABILITY_REGISTRY,
    PublicCapabilityResult,
    get_capability_definition,
    is_workflow_capability,
    missing_required_capability_arguments,
)
from .prompt_assembly import ConversationContextWindow, assemble_harness_prompt
from .skills import build_skill_prompt_block, select_skill_names
from .service import (
    cancel_runtime_run,
    complete_runtime_run,
    execute_capability,
    fail_runtime_run,
    finalize_requested_runtime_cancellation,
    record_runtime_context_trace,
    runtime_cancellation_requested,
    resolve_approval,
)
from contracts.runtime import RuntimeApprovalDecisionType

logger = logging.getLogger(__name__)

# Re-export for type checkers / tests without circular import noise.
ModelUsageObserver = Callable[[ProviderUsageMeasurement | None], None]

HARNESS_MAX_STEPS = 8
HARNESS_MAX_TOOLS_PER_TURN = 1
HARNESS_CAMPAIGN_MAX_STEPS = 16
HARNESS_CAMPAIGN_MAX_TOOLS_PER_TURN = 1
HARNESS_MAX_CONSECUTIVE_TOOL_FAILURES = 3
_LLM_TOOL_RESULT_MAX_CHARS = 2_000

# Messages / capabilities that justify a higher step budget without global YOLO.
_CAMPAIGN_MESSAGE_MARKERS = (
    "全部章节",
    "所有章节",
    "整本",
    "多章节",
    "批量起草",
    "完整起草",
    "整包导出",
    "导出全套",
    "研究并写入",
    "run_section_campaign",
    "section campaign",
    "all sections",
    "full draft",
)
_CAMPAIGN_CAPABILITIES = frozenset(
    {
        "run_section_campaign",
        "web_search",
        "fetch_url_to_project",
        "start_draft_section",
        "write_section",
        "export_deliverable",
        "generate_readiness_pack",
    }
)

# "Test yourself" must not become permission to randomly create, edit, or
# delete customer data. Keep those requests useful by limiting the model to
# read-only diagnostic capabilities unless the user also names a real action.
_DIAGNOSTIC_MESSAGE_MARKERS = (
    "随便调用",
    "随便用",
    "测试工具",
    "测试一下",
    "测试你的",
    "长任务能力",
    "多轮调用",
)
_MUTATING_REQUEST_MARKERS = (
    "创建",
    "删除",
    "上传",
    "写入",
    "起草",
    "导出",
    "配置",
    "修改",
    "更新",
    "提交",
    "审批",
    "同步",
    "抓取",
)
_SAFE_DIAGNOSTIC_CAPABILITIES = frozenset(
    {
        "search_projects",
        "get_project_summary",
        "list_project_bundles",
        "list_sections",
        "get_project_outline",
        "list_pending_reviews",
        "list_requirements",
        "list_claim_review_queue",
        "get_readiness_summary",
        "list_readiness_gaps",
        "list_evidence",
        "list_deliverables",
        "list_documents",
        "get_section_versions",
        "semantic_search",
        "search_bid_wiki",
        "list_knowledge_portfolio",
        "get_runtime_status",
    }
)


def classify_model_failure(exc: Exception) -> PublicRuntimeFailure:
    """Translate provider failures without exposing raw gateway responses."""
    raw = redact_text(str(exc))
    normalized = raw.lower()
    if "supported api model names" in normalized or (
        "invalid_request" in normalized and "model" in normalized
    ):
        return PublicRuntimeFailure(
            "provider_model_incompatible",
            "所选模型与当前提供商端点不兼容。请在模型配置中选择该端点支持的模型后重试。",
        )
    if "response_format" in normalized or "json_schema" in normalized:
        return PublicRuntimeFailure(
            "provider_structured_output_unsupported",
            "当前模型或端点不支持所需的结构化输出。请切换到支持工具调用的兼容模型或端点。",
        )
    if any(marker in normalized for marker in ("invalid api key", "authentication", "unauthorized", "401")):
        return PublicRuntimeFailure(
            "provider_auth_failed",
            "模型提供商认证失败。请检查平台模型配置或自定义提供商密钥。",
        )
    if any(marker in normalized for marker in ("rate limit", "too many requests", "429")):
        return PublicRuntimeFailure(
            "provider_rate_limited",
            "模型服务当前繁忙或已达到提供商限额，请稍后重试。",
        )
    if any(marker in normalized for marker in ("timeout", "timed out", "connection", "connect")):
        return PublicRuntimeFailure(
            "provider_unavailable",
            "模型服务暂时不可用，已停止本次执行。请稍后重试。",
        )
    return PublicRuntimeFailure(
        "provider_request_failed",
        "模型服务暂时无法完成本次请求，已停止执行。请稍后重试或切换模型。",
    )


def public_model_failure_message(exc: Exception) -> str:
    """Compatibility helper for callers that only need the public text."""
    return classify_model_failure(exc).message


def _is_diagnostic_only_request(user_message: str) -> bool:
    text = (user_message or "").strip()
    return bool(text) and any(marker in text for marker in _DIAGNOSTIC_MESSAGE_MARKERS) and not any(
        marker in text for marker in _MUTATING_REQUEST_MARKERS
    )


def resolve_harness_budgets(
    user_message: str,
    *,
    force_campaign: bool = False,
) -> tuple[int, int]:
    """Return (max_steps, max_tools_per_turn) for this turn.

    Default stays tight for safety. Research / multi-section campaign language
    (or an explicit force) raises the ceiling without removing the hard cap.
    """
    text = (user_message or "").strip()
    lowered = text.casefold()
    if force_campaign or any(marker in text or marker in lowered for marker in _CAMPAIGN_MESSAGE_MARKERS):
        return HARNESS_CAMPAIGN_MAX_STEPS, HARNESS_CAMPAIGN_MAX_TOOLS_PER_TURN
    return HARNESS_MAX_STEPS, HARNESS_MAX_TOOLS_PER_TURN

# Minimal OpenAI-compatible argument schemas. Keep these product-facing and
# small; execute_capability remains the real validation boundary.
_TOOL_PARAMETER_SCHEMAS: dict[str, dict[str, Any]] = {
    "search_projects": {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "Optional project name keyword"}},
        "additionalProperties": False,
    },
    "create_demo_workspace": {"type": "object", "properties": {}, "additionalProperties": False},
    "create_project": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Project name"},
            "scenario_package": {"type": "string", "description": "Scenario package key", "default": "bidpilot"},
        },
        "required": ["name"],
        "additionalProperties": False,
    },
    "get_project_summary": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "list_project_bundles": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "list_sections": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "get_project_outline": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "list_pending_reviews": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "submit_review_decision": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "section_id": {"type": "string"},
            "section_version_id": {
                "type": "string",
                "description": "Immutable candidate version selected from list_pending_reviews",
            },
            "decision": {"type": "string", "enum": ["approved", "rejected"]},
            "comment": {"type": "string"},
        },
        "required": ["project_id", "section_id", "section_version_id", "decision"],
        "additionalProperties": False,
    },
    "list_requirements": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "list_claim_review_queue": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "get_readiness_summary": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "list_readiness_gaps": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "kind": {"type": "string", "description": "Gap kind filter", "default": "all"},
        },
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "open_requirement_source": {
        "type": "object",
        "properties": {"requirement_id": {"type": "string"}},
        "required": ["requirement_id"],
        "additionalProperties": False,
    },
    "list_evidence": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "list_deliverables": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "list_documents": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "attach_uploaded_documents": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "attachment_ids": {"type": "array", "items": {"type": "string"}},
            "bundle_id": {"type": "string"},
        },
        "required": ["project_id", "attachment_ids"],
        "additionalProperties": False,
    },
    "get_section_versions": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}, "section_key": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "create_deliverable": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}, "title": {"type": "string"}},
        "required": ["project_id", "title"],
        "additionalProperties": False,
    },
    "start_draft_section": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "section_key": {"type": "string"},
            "provider_config_id": {"type": "string"},
            "reasoning_effort": {"type": "string"},
            "allow_empty_evidence": {
                "type": "boolean",
                "description": (
                    "Set true only when the user explicitly asks to draft without "
                    "uploaded materials (e.g. 自行拟草)."
                ),
            },
        },
        "required": ["project_id", "section_key"],
        "additionalProperties": False,
    },
    "write_section": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "section_key": {
                "type": "string",
                "description": "Outline section_key from get_project_outline/list_sections",
            },
            "content_markdown": {
                "type": "string",
                "description": "Full markdown body to persist as a new section version",
            },
            "title": {
                "type": "string",
                "description": "Optional section title when creating a missing outline chapter",
            },
        },
        "required": ["project_id", "section_key", "content_markdown"],
        "additionalProperties": False,
    },
    "start_redraft_section": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "section_key": {"type": "string"},
            "review_feedback": {
                "type": "string",
                "description": "Human review feedback to guide the redraft",
            },
            "provider_config_id": {"type": "string"},
            "reasoning_effort": {"type": "string"},
        },
        "required": ["project_id", "section_key"],
        "additionalProperties": False,
    },
    "resume_draft_run": {
        "type": "object",
        "properties": {
            "run_id": {"type": "string", "description": "Execution run id awaiting human approval"},
            "decision": {"type": "string", "enum": ["approved", "rejected"]},
            "feedback": {"type": "string", "description": "Optional feedback when rejecting"},
        },
        "required": ["run_id", "decision"],
        "additionalProperties": False,
    },
    "propose_memory_graph": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "memory_record_id": {"type": "string"},
            "provider_config_id": {"type": "string"},
            "reasoning_effort": {"type": "string"},
        },
        "required": ["project_id", "memory_record_id"],
        "additionalProperties": False,
    },
    "get_runtime_status": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "retry_run": {
        "type": "object",
        "properties": {"run_id": {"type": "string"}},
        "required": ["run_id"],
        "additionalProperties": False,
    },
    "export_deliverable": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "deliverable_id": {"type": "string"},
            "format": {"type": "string", "enum": ["docx", "pdf"], "default": "docx"},
        },
        "required": ["deliverable_id"],
        "additionalProperties": False,
    },
    "generate_readiness_pack": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "semantic_search": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "query": {"type": "string"},
            "top_k": {"type": "integer", "minimum": 1, "maximum": 20},
        },
        "required": ["project_id", "query"],
        "additionalProperties": False,
    },
    "web_search": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query for the public web"},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 10},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    "fetch_url_to_project": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "url": {"type": "string", "description": "http(s) URL to download into the project bundle"},
            "filename": {"type": "string"},
            "bundle_id": {"type": "string"},
        },
        "required": ["project_id", "url"],
        "additionalProperties": False,
    },
    "upload_document": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "attachment_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Staged chat attachment IDs to ingest into the project",
            },
            "filename": {"type": "string"},
            "content_base64": {
                "type": "string",
                "description": "Small agent-generated file body (base64), max 10MB",
            },
            "content_type": {"type": "string"},
            "bundle_id": {"type": "string"},
            "bundle_label": {"type": "string"},
        },
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "search_bid_wiki": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}, "query": {"type": "string"}},
        "required": ["project_id", "query"],
        "additionalProperties": False,
    },
    "list_knowledge_portfolio": {"type": "object", "properties": {}, "additionalProperties": False},
    "propose_memory": {
        "type": "object",
        "properties": {
            "body_markdown": {"type": "string"},
            "title": {"type": "string"},
            "scope": {"type": "string"},
            "kind": {"type": "string"},
        },
        "required": ["body_markdown"],
        "additionalProperties": False,
    },
    "forget_memory": {
        "type": "object",
        "properties": {"memory_id": {"type": "string"}},
        "required": ["memory_id"],
        "additionalProperties": False,
    },
    "open_page": {
        "type": "object",
        "properties": {"route": {"type": "string"}},
        "required": ["route"],
        "additionalProperties": False,
    },
    "delete_project": {
        "type": "object",
        "properties": {"project_id": {"type": "string"}},
        "required": ["project_id"],
        "additionalProperties": False,
    },
    "run_section_campaign": {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "mode": {
                "type": "string",
                "enum": ["plan", "framework", "draft_workflow"],
                "description": (
                    "plan: planner-only worklist; "
                    "framework: write short outline-first skeletons into empty sections; "
                    "draft_workflow: start governed draft workflows per empty section"
                ),
            },
            "max_sections": {
                "type": "integer",
                "description": "Max sections to process per wave (1-8, default 3)",
            },
            "auto_continue": {
                "type": "boolean",
                "description": "Process multiple waves in one call until empty or max_waves (default true for framework)",
            },
            "max_waves": {
                "type": "integer",
                "description": "Max waves when auto_continue is true (1-6, default 4)",
            },
            "section_keys": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional explicit section_key list; default = empty template sections",
            },
            "allow_empty_evidence": {
                "type": "boolean",
                "description": "For draft_workflow mode when project has no parsed materials",
            },
            "provider_config_id": {"type": "string"},
            "reasoning_effort": {"type": "string"},
        },
        "required": ["project_id"],
        "additionalProperties": False,
    },
}


def build_capability_tool_specs(*, allowed_names: frozenset[str] | None = None) -> list[dict[str, Any]]:
    """OpenAI-compatible tool specs derived from the product capability registry."""
    tools: list[dict[str, Any]] = []
    for definition in sorted(CAPABILITY_REGISTRY.values(), key=lambda item: item.name):
        if allowed_names is not None and definition.name not in allowed_names:
            continue
        parameters = _TOOL_PARAMETER_SCHEMAS.get(
            definition.name,
            {"type": "object", "properties": {}, "additionalProperties": True},
        )
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": definition.name,
                    "description": f"{definition.label_zh} / {definition.label_en}",
                    "parameters": parameters,
                },
            }
        )
    return tools


def build_turn_summary(tool_names: list[str]) -> str:
    """Rule-based L1 summary. Never spend another model call for this."""
    if not tool_names:
        return "本轮无工具调用"
    counts: dict[str, int] = {}
    for name in tool_names:
        counts[name] = counts.get(name, 0) + 1
    parts: list[str] = []
    for name, count in counts.items():
        try:
            label = get_capability_definition(name).label_zh
        except ValueError:
            label = name
        parts.append(f"{label} ×{count}" if count > 1 else label)
    return " · ".join(parts)


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@dataclass
class _BufferedToolCall:
    tool_call_id: str
    name: str
    arguments: dict[str, Any]


class StreamingHarness:
    """One assistant turn as a streaming multi-step tool loop."""

    def __init__(
        self,
        *,
        db: Session,
        user: CurrentUser,
        run: RuntimeRun,
        conversation_id: str,
        llm: Any,
        provider_type: str,
        provider_source: ProviderSource,
        model: str | None,
        user_message: str,
        conversation_context: list[dict[str, str]] | None = None,
        conversation_summary: str = "",
        conversation_history_truncated: bool = False,
        conversation_window: ConversationContextWindow | None = None,
        memory_context_records: list[dict[str, Any]] | None = None,
        memory_context_version: str | None = None,
        available_attachments: list[dict[str, Any]] | None = None,
        attachment_context: str = "",
        active_project_id: str | None = None,
        pending_input: dict[str, Any] | None = None,
        approval_mode: str = "risky_only",
        provider_config_id: str | None = None,
        reasoning_effort: str | None = None,
        max_steps: int | None = None,
        max_tools_per_turn: int | None = None,
        after_sequence: int = 0,
    ) -> None:
        self.db = db
        self.user = user
        self.runtime_run = run
        self.conversation_id = conversation_id
        self.llm = llm
        self.provider_type = provider_type
        self.provider_source = provider_source
        self.model = model
        self.user_message = user_message
        self.conversation_context = conversation_context or []
        self.conversation_window = conversation_window or ConversationContextWindow(
            summary=conversation_summary,
            recent_turns=tuple(self.conversation_context),
            source_message_count=len(self.conversation_context),
            history_window_truncated=conversation_history_truncated,
            summary_truncated=False,
        )
        self.memory_context_records = memory_context_records or []
        self.memory_context_version = memory_context_version
        self.available_attachments = available_attachments or []
        self.attachment_context = attachment_context
        self.active_project_id = active_project_id
        self.pending_input = pending_input or {}
        self.approval_mode = approval_mode
        self.provider_config_id = provider_config_id
        self.reasoning_effort = reasoning_effort
        default_steps, _default_tools = resolve_harness_budgets(user_message)
        self.max_steps = max(1, max_steps if max_steps is not None else default_steps)
        # Tool calls remain strictly result-driven: one capability per model
        # turn. Long tasks use more turns or a purpose-built campaign tool.
        self.max_tools_per_turn = 1
        self.after_sequence = after_sequence
        self._active_reservation_keys: list[str] = []
        self._cursor = after_sequence
        self._streamed_text = False
        self._consecutive_tool_failures = 0
        self._emitted_end = False
        self._context_trace: dict[str, Any] | None = None
        self._diagnostic_only = _is_diagnostic_only_request(user_message)
        self._allowed_capability_names = (
            _SAFE_DIAGNOSTIC_CAPABILITIES
            if self._diagnostic_only
            else frozenset(CAPABILITY_REGISTRY)
        )

    async def run(self) -> AsyncGenerator[str, None]:
        register_default_recovery_hooks()
        # Inject workflow wakes from durable notifications. API restarts cannot
        # lose this context because Worker commits the notification with the
        # terminal RuntimeEvent. They remain untrusted model-facing data.
        notifications = collect_completed_notifications(
            self.db,
            conversation_id=self.conversation_id,
            user_id=self.user.id,
        )
        messages = self._initial_messages(background_notifications=notifications)
        self._persist_context_trace()
        tools = build_capability_tool_specs(allowed_names=self._allowed_capability_names)
        bound = self.llm.bind_tools(tools)
        hook_ctx = HookContext(
            conversation_id=self.conversation_id,
            runtime_run_id=self.runtime_run.id,
            user_id=self.user.id,
            project_id=self.active_project_id,
        )
        default_hook_registry.trigger("UserPromptSubmit", hook_ctx, self.user_message)

        try:
            for step in range(self.max_steps):
                if runtime_cancellation_requested(self.db, self.runtime_run.id):
                    async for event in self._emit_requested_cancellation():
                        yield event
                    return
                hook_ctx.step = step
                turn_id = f"turn-{step + 1}"
                yield _sse(
                    "assistant.turn_started",
                    {
                        "runtime_run_id": self.runtime_run.id,
                        "turn_id": turn_id,
                        "step": step + 1,
                        "state": "thinking",
                    },
                )

                text_parts: list[str] = []
                tool_calls: list[_BufferedToolCall] = []
                usage_holder: dict[str, ProviderUsageMeasurement | None] = {"measurement": None}
                self._reserve_model_capacity()
                try:
                    async for event in self._stream_model_step(
                        bound,
                        messages,
                        turn_id,
                        text_parts,
                        tool_calls,
                        usage_holder,
                    ):
                        yield event
                    # Prefer provider-reported usage; if streaming omitted it,
                    # release the hold instead of parking 8k–24k as "uncertain".
                    self._observe_model_usage(usage_holder.get("measurement"))
                except Exception:
                    self._mark_active_reservations_uncertain()
                    raise

                if runtime_cancellation_requested(self.db, self.runtime_run.id):
                    async for event in self._emit_requested_cancellation():
                        yield event
                    return

                if not tool_calls:
                    final_text = "".join(text_parts).strip() or "我可以继续帮你处理这个请求。"
                    force_reason = default_hook_registry.first_blocking(
                        "Stop",
                        hook_ctx,
                        open_tools=0,
                        max_steps=self.max_steps,
                        step=step,
                    )
                    if force_reason and step + 1 < self.max_steps:
                        hook_ctx.metadata["stop_hook_active"] = True
                        messages.append(AIMessage(content=final_text))
                        messages.append(HumanMessage(content=str(force_reason)))
                        default_hook_registry.trigger("TurnEnd", hook_ctx, final_text=final_text)
                        continue
                    if not self._streamed_text:
                        yield _sse(
                            "assistant.message",
                            {
                                "runtime_run_id": self.runtime_run.id,
                                "turn_id": turn_id,
                                "content": final_text,
                                "state": "completed",
                            },
                        )
                        self._streamed_text = True
                    save_message(self.db, self.conversation_id, "assistant", final_text)
                    complete_runtime_run(self.db, self.runtime_run.id, final_text)
                    async for event in self._flush_new_events(skip_message_completed=True):
                        yield event
                    return

                # Raise budget mid-turn when the model starts a campaign/research wave.
                if any(item.name in _CAMPAIGN_CAPABILITIES for item in tool_calls):
                    self.max_steps = max(self.max_steps, HARNESS_CAMPAIGN_MAX_STEPS)
                    self.max_tools_per_turn = HARNESS_CAMPAIGN_MAX_TOOLS_PER_TURN

                # Keep the assistant message that requested tools in the transcript.
                ai_tool_message = AIMessage(
                    content="".join(text_parts),
                    tool_calls=[
                        {
                            "id": item.tool_call_id,
                            "name": item.name,
                            "args": item.arguments,
                        }
                        for item in tool_calls[: self.max_tools_per_turn]
                    ],
                )
                messages.append(ai_tool_message)

                executed_names: list[str] = []
                for item in tool_calls[: self.max_tools_per_turn]:
                    if runtime_cancellation_requested(self.db, self.runtime_run.id):
                        async for event in self._emit_requested_cancellation():
                            yield event
                        return
                    blocked = default_hook_registry.first_blocking(
                        "PreToolUse",
                        hook_ctx,
                        tool_name=item.name,
                        arguments=item.arguments,
                    )
                    if blocked is not None:
                        try:
                            title = get_capability_definition(item.name).label_zh
                        except ValueError:
                            title = item.name
                        message = "该工具请求被当前安全策略阻止。"
                        messages.append(
                            ToolMessage(
                                content=json.dumps(
                                    {"error": message, "blocked_by_hook": True},
                                    ensure_ascii=False,
                                )[:_LLM_TOOL_RESULT_MAX_CHARS],
                                tool_call_id=item.tool_call_id,
                            )
                        )
                        self._consecutive_tool_failures += 1
                        yield _sse(
                            "assistant.tool_failed",
                            {
                                "runtime_run_id": self.runtime_run.id,
                                "turn_id": turn_id,
                                "tool_call_id": item.tool_call_id,
                                "tool_name": item.name,
                                "title": title,
                                "error_code": "capability_policy_blocked",
                                "error_message": message,
                                "state": "failed",
                            },
                        )
                        async for event in self._stop_after_repeated_tool_failures():
                            yield event
                        if self._emitted_end:
                            return
                        continue
                    paused_for_user_input = False
                    async for event in self._execute_one_tool(item, turn_id, messages, executed_names):
                        yield event
                        default_hook_registry.trigger(
                            "PostToolUse",
                            hook_ctx,
                            tool_name=item.name,
                            arguments=item.arguments,
                        )
                        # The tool coroutine owns its terminal end event for
                        # confirmations and missing input alike.
                        if event.startswith("event: assistant.end") and (
                            "needs_confirmation" in event or "needs_input" in event
                        ):
                            paused_for_user_input = True
                        if event.startswith("event: assistant.end") and '"state": "failed"' in event:
                            return
                    if paused_for_user_input:
                        return
                    if runtime_cancellation_requested(self.db, self.runtime_run.id):
                        async for event in self._emit_requested_cancellation():
                            yield event
                        return

                summary = build_turn_summary(executed_names)
                default_hook_registry.trigger(
                    "TurnEnd",
                    hook_ctx,
                    tools=executed_names,
                    summary=summary,
                )
                yield _sse(
                    "assistant.turn_finished",
                    {
                        "runtime_run_id": self.runtime_run.id,
                        "turn_id": turn_id,
                        "summary": summary,
                        "state": "thinking",
                    },
                )

            message = "为避免重复执行，我已达到本次任务的操作上限。请确认下一步后再继续。"
            if not self._streamed_text:
                yield _sse(
                    "assistant.message",
                    {
                        "runtime_run_id": self.runtime_run.id,
                        "content": message,
                        "state": "completed",
                    },
                )
            save_message(self.db, self.conversation_id, "assistant", message)
            complete_runtime_run(self.db, self.runtime_run.id, message)
            async for event in self._flush_new_events(skip_message_completed=True):
                yield event
        except UsageLimitExceeded as exc:
            self._mark_active_reservations_uncertain()
            message = str(exc)
            try:
                fail_runtime_run(self.db, self.runtime_run.id, message, error_code="organization_token_budget_exhausted")
            except ValueError:
                pass
            save_message(self.db, self.conversation_id, "assistant", message)
            async for event in self._flush_new_events():
                yield event
        except Exception as exc:
            self._mark_active_reservations_uncertain()
            logger.warning(
                "Harness model loop failed: runtime_run=%s provider_type=%s error_type=%s",
                self.runtime_run.id,
                self.provider_type,
                type(exc).__name__,
            )
            failure = classify_model_failure(exc)
            try:
                fail_runtime_run(
                    self.db,
                    self.runtime_run.id,
                    failure.message,
                    error_code=failure.error_code,
                )
            except ValueError:
                pass
            save_message(self.db, self.conversation_id, "assistant", failure.message)
            async for event in self._flush_new_events():
                yield event

    async def resume_approval(
        self,
        *,
        approval_id: str,
        approved: bool,
        tool_name: str,
        edited_arguments: dict[str, Any] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Resume a paused approval with a single clean tool lifecycle + end."""
        try:
            if not approved:
                from contracts.runtime import RuntimeApprovalDecisionType as Decision

                resolve_approval(
                    self.db,
                    self.user,
                    approval_id=approval_id,
                    decision=Decision.REJECT,
                )
                clear_task_state(self.db, self.conversation_id)
                message = "已取消这次操作。"
                cancel_runtime_run(self.db, self.runtime_run.id, message)
                save_message(self.db, self.conversation_id, "assistant", message)
                async for event in self._flush_new_events(
                    skip_message_completed=True,
                    skip_capability_started=True,
                    skip_run_terminal=True,
                ):
                    yield event
                yield _sse(
                    "assistant.message",
                    {
                        "runtime_run_id": self.runtime_run.id,
                        "content": message,
                        "state": "completed",
                    },
                )
                async for event in self._emit_end_once(state="completed"):
                    yield event
                return

            # Emit started first so UI never sees succeeded-before-started.
            try:
                title = get_capability_definition(tool_name).label_zh
            except Exception:
                title = tool_name
            yield _sse(
                "assistant.tool_started",
                {
                    "runtime_run_id": self.runtime_run.id,
                    "tool_name": tool_name,
                    "title": title,
                    "arguments": redact_arguments(edited_arguments or {}),
                    "state": "executing_tool",
                },
            )

            # Typed confirmation and other user edits arrive as confirmation.arguments.
            # Prefer EDIT so execute_capability sees confirmation_text / edited fields.
            if edited_arguments:
                execution = resolve_approval(
                    self.db,
                    self.user,
                    approval_id=approval_id,
                    decision=RuntimeApprovalDecisionType.EDIT,
                    edited_arguments=edited_arguments,
                )
            else:
                execution = resolve_approval(
                    self.db,
                    self.user,
                    approval_id=approval_id,
                    decision=RuntimeApprovalDecisionType.APPROVE,
                )
            clear_task_state(self.db, self.conversation_id)
            result = execution.result or PublicCapabilityResult("操作已完成。", {})
            self._maybe_bind_project(tool_name, result.payload)
            # Suppress durable started/succeeded/run.completed remaps — we own the
            # live SSE lifecycle here to avoid double tool_succeeded + double end.
            async for event in self._flush_new_events(
                skip_message_completed=True,
                skip_capability_started=True,
                skip_capability_succeeded=True,
                skip_run_terminal=True,
            ):
                yield event
            yield _sse(
                "assistant.tool_succeeded",
                {
                    "runtime_run_id": self.runtime_run.id,
                    "tool_name": tool_name,
                    "result": result.payload,
                    "summary": result.summary,
                    "state": "completed",
                },
            )
            save_message(self.db, self.conversation_id, "assistant", result.summary)
            complete_runtime_run(
                self.db,
                self.runtime_run.id,
                result.summary,
                result_json={"summary": result.summary, "payload": result.payload},
            )
            async for event in self._flush_new_events(
                skip_message_completed=True,
                skip_capability_started=True,
                skip_capability_succeeded=True,
                skip_run_terminal=True,
            ):
                yield event
            yield _sse(
                "assistant.message",
                {
                    "runtime_run_id": self.runtime_run.id,
                    "content": result.summary,
                    "state": "completed",
                },
            )
            async for event in self._emit_end_once(state="completed"):
                yield event
        except Exception as exc:
            failure = classify_capability_failure(exc)
            message = f"执行失败：{failure.message}"
            # Keep the failure visible as a tool card, but do not strand the UI
            # without a clear next step. Typed confirmation mismatches should
            # tell the user exactly what to type, not look like a fake sandbox.
            yield _sse(
                "assistant.tool_failed",
                {
                    "runtime_run_id": self.runtime_run.id,
                    "tool_name": tool_name,
                    "error_code": failure.error_code,
                    "error_message": failure.message,
                    "state": "failed",
                },
            )
            try:
                fail_runtime_run(
                    self.db,
                    self.runtime_run.id,
                    message,
                    error_code=failure.error_code,
                )
            except ValueError:
                pass
            guidance = message
            raw_error = str(exc)
            if "完整项目名称" in raw_error or "confirmation" in raw_error.lower():
                guidance = (
                    f"{message}\n\n"
                    "这不是沙箱假失败：删除属于破坏性操作，即使在「完全访问」下也需要输入完整项目名称确认。"
                    "请再次发起删除，并在确认框中输入完整项目名。"
                )
            save_message(self.db, self.conversation_id, "assistant", guidance)
            async for event in self._flush_new_events(
                skip_message_completed=True,
                skip_capability_started=True,
                skip_run_terminal=True,
            ):
                yield event
            yield _sse(
                "assistant.message",
                {
                    "runtime_run_id": self.runtime_run.id,
                    "content": guidance,
                    "state": "failed",
                },
            )
            async for event in self._emit_end_once(state="failed"):
                yield event

    def _initial_messages(
        self,
        *,
        background_notifications: list[dict[str, Any]],
    ) -> list[Any]:
        capability_list = "、".join(
            f"{item.name}（{item.label_zh}）"
            for item in sorted(CAPABILITY_REGISTRY.values(), key=lambda value: value.name)
            if item.name in self._allowed_capability_names
        )
        system_policy = (
            "你是 BidPilot 的平台执行助手。你可以回答问题，也可以调用注册工具。\n"
            "规则：\n"
            "1. 只使用提供的工具；禁止虚构执行结果。\n"
            "2. 每个回合最多调用一个工具；拿到结果后再决定下一步，禁止一次并发或串联猜测多个工具。\n"
            "3. 信息不足时先用中文追问一个最关键字段，不要瞎猜 ID。\n"
            "4. 变更类操作由服务端审批，你仍然可以提出 tool call。\n"
            "5. 若 active_project_id 存在，项目范围内操作优先使用它。\n"
            "6. 工具结果返回后，用简洁中文总结并推进下一步。\n"
            "7. 写作/起草任务：先 get_project_outline 或 list_sections 拿到 section_key，"
            "再 start_draft_section 或 write_section；禁止只在聊天里写长文代替章节写入。"
            "用户说「自行完成/拟草」时：无资料用 write_section 直接写入；有资料用 start_draft_section。\n"
            "8. outline/sections 工具结果里的 sections[].section_key 必须原样用于后续工具，"
            "不要声称「没有 section_key」。\n"
            "9. search_projects 结果若存在同名项目，必须用 projects[].id 或 short_id 区分；"
            "禁止发明「(1)/(2)」标签；删除/打开前先复述目标 id。\n"
            "10. 若上一轮已进入待确认删除/写入，优先等待用户确认，不要重复搜索或重新发起同类操作。\n"
            "11. 外部研究：用 web_search 找来源；需要入库时用 fetch_url_to_project；"
            "聊天附件入库用 upload_document(attachment_ids=...)。长工作流完成后会有后台通知，"
            "收到 <task_notification> 后继续，不要空转轮询。\n"
            "12. 多章节战役：用户要求「全部章节/整本/批量起草」时，优先 run_section_campaign"
            "（mode=framework 先写骨架；有资料用 draft_workflow）。不要在一回合里手写 20 章长文。"
            "campaign 返回 remaining_section_keys/has_more 时，同一回合或下一波继续同一 project_id，"
            "直到 has_more=false；不要停在第一波就结束。\n"
            "13. 删除：用户明确给出 project_id 或唯一 short_id 要求删除时，直接 delete_project，"
            "不要先 search_projects / get_project_summary 兜圈子；服务端会弹出 typed confirmation。\n"
            "14. 错误恢复：get_project_outline/list_sections 因坏 id 失败时，先 search_projects；"
            "若结果仅 1 个可访问项目，自动用该 id 重试一次 outline，不要只停在列表询问。\n"
            + (
                "15. 当前请求是安全诊断；只能执行提供的只读工具，禁止创建、删除、写入、上传、起草或导出。\n"
                if self._diagnostic_only
                else ""
            )
            + f"可用工具：{capability_list}"
        )
        skill_block = build_skill_prompt_block(self.user_message)
        assembly = assemble_harness_prompt(
            system_policy=system_policy,
            actor_id=self.user.id,
            org_id=self.user.org_id,
            actor_role=self.user.role,
            active_project_id=self.active_project_id,
            approval_mode=self.approval_mode,
            selected_skill_names=select_skill_names(self.user_message),
            skill_prompt_block=skill_block,
            pending_input=self.pending_input,
            conversation=self.conversation_window,
            staged_attachments=self.available_attachments,
            attachment_context=self.attachment_context,
            memory_context_records=self.memory_context_records,
            memory_version=self.memory_context_version,
            background_notifications=background_notifications,
            user_message=self.user_message,
        )
        self._context_trace = assembly.trace
        return list(assembly.messages)

    def _persist_context_trace(self) -> None:
        if self._context_trace is None:
            return
        try:
            record_runtime_context_trace(self.db, self.runtime_run, trace=self._context_trace)
        except Exception:
            rollback = getattr(self.db, "rollback", None)
            if callable(rollback):
                rollback()
            logger.warning(
                "Harness context trace persistence failed: runtime_run=%s",
                self.runtime_run.id,
            )

    async def _stream_model_step(
        self,
        bound: Any,
        messages: list[Any],
        turn_id: str,
        text_parts: list[str],
        tool_calls: list[_BufferedToolCall],
        usage_holder: dict[str, ProviderUsageMeasurement | None] | None = None,
    ) -> AsyncGenerator[str, None]:
        # Prefer token streaming; fall back to one-shot invoke for test doubles.
        if hasattr(bound, "astream"):
            assembled_tools: dict[int, dict[str, Any]] = {}
            async for chunk in bound.astream(messages):
                measurement = normalize_langchain_usage(getattr(chunk, "usage_metadata", None))
                if measurement is None:
                    measurement = normalize_langchain_usage(
                        (getattr(chunk, "response_metadata", None) or {}).get("token_usage")
                        if isinstance(getattr(chunk, "response_metadata", None), dict)
                        else None
                    )
                if measurement is not None and usage_holder is not None:
                    usage_holder["measurement"] = measurement
                content = getattr(chunk, "content", None)
                if isinstance(content, str) and content:
                    text_parts.append(content)
                    self._streamed_text = True
                    yield _sse(
                        "assistant.message",
                        {
                            "runtime_run_id": self.runtime_run.id,
                            "turn_id": turn_id,
                            "content": content,
                            "state": "thinking",
                        },
                    )
                chunk_tool_calls = getattr(chunk, "tool_call_chunks", None) or []
                for piece in chunk_tool_calls:
                    index = int(piece.get("index") or 0)
                    bucket = assembled_tools.setdefault(index, {"id": "", "name": "", "args": ""})
                    if piece.get("id"):
                        bucket["id"] = str(piece["id"])
                    if piece.get("name"):
                        bucket["name"] = str(piece["name"])
                    if piece.get("args"):
                        bucket["args"] = f"{bucket['args']}{piece['args']}"
            for index in sorted(assembled_tools):
                bucket = assembled_tools[index]
                name = (bucket.get("name") or "").strip()
                if not name:
                    continue
                args_raw = bucket.get("args") or "{}"
                try:
                    arguments = json.loads(args_raw) if isinstance(args_raw, str) else dict(args_raw or {})
                except json.JSONDecodeError:
                    arguments = {}
                if not isinstance(arguments, dict):
                    arguments = {}
                tool_calls.append(
                    _BufferedToolCall(
                        tool_call_id=str(bucket.get("id") or f"call_{uuid4().hex[:12]}"),
                        name=name,
                        arguments=arguments,
                    )
                )
            return

        # Non-streaming fallback for unit tests / providers without astream.
        response = bound.invoke(messages) if hasattr(bound, "invoke") else await bound.ainvoke(messages)
        if usage_holder is not None:
            measurement = normalize_langchain_usage(getattr(response, "usage_metadata", None))
            if measurement is None and isinstance(getattr(response, "response_metadata", None), dict):
                measurement = normalize_langchain_usage(
                    (response.response_metadata or {}).get("token_usage")
                )
            usage_holder["measurement"] = measurement
        content = getattr(response, "content", "") or ""
        if isinstance(content, str) and content:
            text_parts.append(content)
            self._streamed_text = True
            yield _sse(
                "assistant.message",
                {
                    "runtime_run_id": self.runtime_run.id,
                    "turn_id": turn_id,
                    "content": content,
                    "state": "thinking",
                },
            )
        for tc in getattr(response, "tool_calls", None) or []:
            if isinstance(tc, dict):
                name = str(tc.get("name") or "")
                raw_args = tc.get("args")
                args = {str(key): value for key, value in raw_args.items()} if isinstance(raw_args, dict) else {}
                tool_call_id = str(tc.get("id") or f"call_{uuid4().hex[:12]}")
            else:
                name = str(getattr(tc, "name", "") or "")
                raw_args = getattr(tc, "args", {}) or {}
                args = {str(key): value for key, value in raw_args.items()} if isinstance(raw_args, dict) else {}
                tool_call_id = str(getattr(tc, "id", None) or f"call_{uuid4().hex[:12]}")
            if name:
                tool_calls.append(_BufferedToolCall(tool_call_id=tool_call_id, name=name, arguments=args))

    async def _execute_one_tool(
        self,
        item: _BufferedToolCall,
        turn_id: str,
        messages: list[Any],
        executed_names: list[str],
    ) -> AsyncGenerator[str, None]:
        arguments = dict(item.arguments)
        if item.name not in self._allowed_capability_names:
            message = (
                "本次是安全诊断，只允许执行只读检查。"
                "请明确说明需要创建、上传、写入或删除的业务目标后再执行。"
                if self._diagnostic_only and item.name in CAPABILITY_REGISTRY
                else "请求了不可用的工具，请调整操作目标后重试。"
            )
            self._consecutive_tool_failures += 1
            messages.append(
                ToolMessage(
                    content=json.dumps({"error": message}, ensure_ascii=False),
                    tool_call_id=item.tool_call_id,
                )
            )
            yield _sse(
                "assistant.tool_failed",
                {
                    "runtime_run_id": self.runtime_run.id,
                    "turn_id": turn_id,
                    "tool_call_id": item.tool_call_id,
                    "tool_name": item.name,
                    "error_code": (
                        "capability_policy_blocked"
                        if self._diagnostic_only and item.name in CAPABILITY_REGISTRY
                        else "capability_unavailable"
                    ),
                    "error_message": message,
                    "state": "failed",
                },
            )
            async for event in self._stop_after_repeated_tool_failures():
                yield event
            return
        if self.active_project_id and "project_id" not in arguments:
            # Prefer durable conversation scope when the model omits it.
            schema = _TOOL_PARAMETER_SCHEMAS.get(item.name, {})
            properties = schema.get("properties") if isinstance(schema, dict) else {}
            if isinstance(properties, dict) and "project_id" in properties:
                arguments["project_id"] = self.active_project_id

        if item.name in {"start_draft_section", "start_redraft_section", "propose_memory_graph"}:
            if self.provider_config_id and not arguments.get("provider_config_id"):
                arguments["provider_config_id"] = self.provider_config_id
            if self.reasoning_effort and not arguments.get("reasoning_effort"):
                arguments["reasoning_effort"] = self.reasoning_effort

        missing: tuple[str, ...] = ()
        try:
            missing = missing_required_capability_arguments(item.name, arguments)
        except Exception:
            missing = ()
        if missing:
            message = (
                "请告诉我项目名称。"
                if item.name == "create_project" and missing == ("name",)
                else f"还需要补充：{'、'.join(missing)}"
            )
            # Missing input is a durable pause boundary, not a failed tool.
            # Persist only the capability and validated missing fields so the
            # next Harness turn can continue without replaying this call.
            set_task_state(
                self.db,
                self.conversation_id,
                status="needs_input",
                tool_name=item.name,
                arguments=arguments,
                missing_fields=missing,
            )
            save_message(self.db, self.conversation_id, "assistant", message)
            complete_runtime_run(self.db, self.runtime_run.id, message)
            yield _sse(
                "assistant.missing_input",
                {
                    "runtime_run_id": self.runtime_run.id,
                    "turn_id": turn_id,
                    "tool_call_id": item.tool_call_id,
                    "tool_name": item.name,
                    "missing_fields": list(missing),
                    "message": message,
                    "state": "needs_input",
                },
            )
            yield _sse(
                "assistant.message",
                {
                    "runtime_run_id": self.runtime_run.id,
                    "turn_id": turn_id,
                    "content": message,
                    "state": "needs_input",
                },
            )
            async for event in self._flush_new_events(
                skip_message_completed=True,
                skip_run_terminal=True,
            ):
                yield event
            async for event in self._emit_end_once(state="needs_input"):
                yield event
            return

        # Once all required business fields are present, the pending-input
        # pause has served its purpose. Clear it before policy evaluation so a
        # subsequent approval pause cannot leave stale missing-field state.
        if self.pending_input.get("capability_name") == item.name:
            clear_task_state(self.db, self.conversation_id)
            self.pending_input = {}

        action_key = f"harness:{turn_id}:{item.tool_call_id}:{item.name}"
        try:
            definition = get_capability_definition(item.name)
        except ValueError:
            message = "请求了不可用的工具，请调整操作目标后重试。"
            self._consecutive_tool_failures += 1
            messages.append(
                ToolMessage(
                    content=json.dumps({"error": message}, ensure_ascii=False),
                    tool_call_id=item.tool_call_id,
                )
            )
            yield _sse(
                "assistant.tool_failed",
                {
                    "runtime_run_id": self.runtime_run.id,
                    "turn_id": turn_id,
                    "tool_call_id": item.tool_call_id,
                    "tool_name": item.name,
                    "error_code": "capability_unavailable",
                    "error_message": message,
                    "state": "failed",
                },
            )
            async for event in self._stop_after_repeated_tool_failures():
                yield event
            return

        # Single live UI started event. Durable capability.started is suppressed on
        # flush so the client does not render a second ghost tool card.
        yield _sse(
            "assistant.tool_started",
            {
                "runtime_run_id": self.runtime_run.id,
                "turn_id": turn_id,
                "tool_call_id": item.tool_call_id,
                "tool_name": item.name,
                "title": definition.label_zh,
                "arguments": redact_arguments(arguments),
                "state": "executing_tool",
            },
        )

        try:
            execution = execute_capability(
                self.db,
                self.user,
                run_id=self.runtime_run.id,
                capability_name=item.name,
                arguments=arguments,
                action_key=action_key,
            )
        except Exception as exc:
            failure = classify_capability_failure(exc)
            self._consecutive_tool_failures += 1
            messages.append(
                ToolMessage(
                    content=json.dumps({"error": failure.message}, ensure_ascii=False)[:_LLM_TOOL_RESULT_MAX_CHARS],
                    tool_call_id=item.tool_call_id,
                )
            )
            yield _sse(
                "assistant.tool_failed",
                {
                    "runtime_run_id": self.runtime_run.id,
                    "turn_id": turn_id,
                    "tool_call_id": item.tool_call_id,
                    "tool_name": item.name,
                    "title": definition.label_zh,
                    "error_code": failure.error_code,
                    "error_message": failure.message,
                    "state": "failed",
                },
            )
            async for event in self._flush_new_events(
                skip_capability_started=True,
                skip_capability_failed=True,
            ):
                yield event
            async for event in self._stop_after_repeated_tool_failures():
                yield event
            return

        if execution.approval is not None:
            async for event in self._flush_new_events(skip_capability_started=True):
                yield event
            async for event in self._emit_end_once(state="needs_confirmation"):
                yield event
            return

        if execution.action.status == "denied":
            message = execution.action.error_message or "操作被拒绝。"
            self._consecutive_tool_failures += 1
            messages.append(
                ToolMessage(
                    content=json.dumps({"error": message}, ensure_ascii=False)[:_LLM_TOOL_RESULT_MAX_CHARS],
                    tool_call_id=item.tool_call_id,
                )
            )
            async for event in self._flush_new_events(skip_capability_started=True):
                yield event
            async for event in self._stop_after_repeated_tool_failures():
                yield event
            return

        result = execution.result or PublicCapabilityResult("操作已完成。", {})
        executed_names.append(item.name)
        self._consecutive_tool_failures = 0
        self._maybe_bind_project(item.name, result.payload)
        if item.name in {"create_project", "create_demo_workspace"}:
            created_id = result.payload.get("id")
            if isinstance(created_id, str) and created_id:
                self.active_project_id = created_id
        llm_content = json.dumps(
            {"summary": result.summary, "payload": result.payload},
            ensure_ascii=False,
        )[:_LLM_TOOL_RESULT_MAX_CHARS]
        messages.append(ToolMessage(content=llm_content, tool_call_id=item.tool_call_id))
        if is_workflow_capability(item.name):
            yield _sse(
                "assistant.workflow_started",
                {
                    "runtime_run_id": self.runtime_run.id,
                    "turn_id": turn_id,
                    "tool_call_id": item.tool_call_id,
                    "tool_name": item.name,
                    "title": definition.label_zh,
                    "arguments": redact_arguments(arguments),
                    "result": result.payload,
                    "state": "running_workflow",
                },
            )
        yield _sse(
            "assistant.tool_succeeded",
            {
                "runtime_run_id": self.runtime_run.id,
                "turn_id": turn_id,
                "tool_call_id": item.tool_call_id,
                "tool_name": item.name,
                "title": definition.label_zh,
                "result": result.payload,
                "summary": result.summary,
                "state": "completed",
            },
        )
        async for event in self._flush_new_events(
            skip_capability_started=True,
            skip_capability_succeeded=True,
        ):
            yield event

    def _maybe_bind_project(self, capability_name: str, payload: dict[str, Any]) -> None:
        if capability_name not in {"create_project", "create_demo_workspace"}:
            return
        project_id = payload.get("id")
        if isinstance(project_id, str) and project_id:
            bind_conversation_project_context(
                self.db,
                conversation_id=self.conversation_id,
                user_id=self.user.id,
                project_id=project_id,
            )

    async def _emit_end_once(self, *, state: str) -> AsyncGenerator[str, None]:
        if self._emitted_end:
            return
        self._emitted_end = True
        yield _sse(
            "assistant.end",
            {
                "conversation_id": self.conversation_id,
                "runtime_run_id": self.runtime_run.id,
                "state": state,
            },
        )

    async def _emit_requested_cancellation(self) -> AsyncGenerator[str, None]:
        """Finalize a browser/API cancellation only at a model or tool boundary."""
        run = finalize_requested_runtime_cancellation(self.db, self.runtime_run.id)
        if run.status != "cancelled":
            return
        message = str((run.result_json or {}).get("message") or "已取消这次操作。")
        save_message(self.db, self.conversation_id, "assistant", message)
        async for event in self._flush_new_events():
            yield event
        # The terminal RuntimeEvent renders assistant.end during the flush.
        self._emitted_end = True

    async def _stop_after_repeated_tool_failures(self) -> AsyncGenerator[str, None]:
        """End a Harness turn after a bounded run of rejected/failed tools."""
        if self._consecutive_tool_failures < HARNESS_MAX_CONSECUTIVE_TOOL_FAILURES:
            return

        message = "连续多次工具执行失败，我先停在这里。请换一种说法或检查项目上下文后再试。"
        save_message(self.db, self.conversation_id, "assistant", message)
        try:
            fail_runtime_run(
                self.db,
                self.runtime_run.id,
                message,
                error_code="harness_tool_failures",
            )
        except ValueError:
            # A concurrent cancellation can win the terminal transition. The
            # regular replay path will render that durable terminal event.
            return

        # The live tool failure was already emitted above. Suppress its durable
        # replay while still persisting the final message/run for reconnects.
        async for event in self._flush_new_events(
            skip_message_completed=True,
            skip_capability_started=True,
            skip_capability_failed=True,
            skip_run_terminal=True,
        ):
            yield event
        yield _sse(
            "assistant.message",
            {
                "runtime_run_id": self.runtime_run.id,
                "content": message,
                "state": "failed",
            },
        )
        async for event in self._emit_end_once(state="failed"):
            yield event

    async def _flush_new_events(
        self,
        *,
        skip_message_completed: bool = False,
        skip_capability_started: bool = False,
        skip_capability_succeeded: bool = False,
        skip_capability_failed: bool = False,
        skip_run_terminal: bool = False,
    ) -> AsyncGenerator[str, None]:
        from .assistant_adapter import _render_runtime_event
        from .events import list_events_after
        from contracts.runtime import RuntimeEventType

        for event in list_events_after(self.db, self.runtime_run.id, after_sequence=self._cursor):
            self._cursor = max(self._cursor, int(event.sequence))
            if (
                skip_message_completed
                and event.event_type == RuntimeEventType.MESSAGE_COMPLETED.value
            ):
                # Text was already streamed as assistant.message deltas; do not
                # re-append the durable final message into the live transcript.
                continue
            if (
                skip_capability_started
                and event.event_type == RuntimeEventType.CAPABILITY_STARTED.value
            ):
                # Harness already emitted live assistant.tool_started for this action.
                continue
            if (
                skip_capability_started
                and event.event_type == RuntimeEventType.APPROVAL_RESOLVED.value
            ):
                # Approval resume path already emitted live tool_started; durable
                # APPROVAL_RESOLVED would remap to a second started card.
                continue
            if (
                skip_capability_succeeded
                and event.event_type == RuntimeEventType.CAPABILITY_SUCCEEDED.value
            ):
                # Approval resume path owns a single tool_succeeded event.
                continue
            if (
                skip_capability_failed
                and event.event_type == RuntimeEventType.CAPABILITY_FAILED.value
            ):
                # The harness already emitted a correlated live tool_failed event.
                continue
            if skip_run_terminal and event.event_type in {
                RuntimeEventType.RUN_COMPLETED.value,
                RuntimeEventType.RUN_FAILED.value,
                RuntimeEventType.RUN_CANCELLED.value,
            }:
                # Avoid durable run.* remapping into a second assistant.end.
                continue
            for rendered in _render_runtime_event(event, self.conversation_id):
                # If a rendered end slipped through, still dedupe.
                if rendered.startswith("event: assistant.end"):
                    if self._emitted_end:
                        continue
                    self._emitted_end = True
                yield rendered

    def _reserve_model_capacity(self) -> None:
        reservation_key = f"assistant:{self.runtime_run.id}:{uuid4()}"
        reservation = reserve_assistant_model_tokens(
            self.db,
            user_id=self.user.id,
            org_id=self.user.org_id,
            provider_source=self.provider_source,
            reservation_key=reservation_key,
            project_id=self.runtime_run.project_id,
            runtime_run_id=self.runtime_run.id,
        )
        if reservation is None:
            return
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self._active_reservation_keys.append(reservation_key)

    def _observe_model_usage(self, measurement: ProviderUsageMeasurement | None) -> None:
        reservation_key = self._active_reservation_keys.pop() if self._active_reservation_keys else None
        try:
            if measurement is not None:
                record_model_usage(
                    self.db,
                    org_id=self.user.org_id,
                    user_id=self.user.id,
                    project_id=self.runtime_run.project_id,
                    runtime_run_id=self.runtime_run.id,
                    provider_source=self.provider_source.value,  # type: ignore[arg-type]
                    provider_type=self.provider_type,
                    provider_config_id=self.runtime_run.provider_config_id,
                    model_name=self.model or self.runtime_run.model or "platform-default",
                    workload="assistant_harness",
                    measurement=measurement,
                )
            if reservation_key is not None:
                if measurement is None:
                    # Streaming providers often omit usage metadata. Releasing the
                    # preflight hold is safer than parking 8k–24k as "uncertain",
                    # which was exhausting the monthly ceiling after a few turns.
                    release_model_reservation(
                        self.db,
                        org_id=self.user.org_id,
                        reservation_key=reservation_key,
                    )
                else:
                    settle_model_reservation(
                        self.db,
                        org_id=self.user.org_id,
                        reservation_key=reservation_key,
                    )
            if measurement is not None or reservation_key is not None:
                self.db.commit()
        except Exception:
            self.db.rollback()
            if reservation_key is not None:
                try:
                    release_model_reservation(
                        self.db,
                        org_id=self.user.org_id,
                        reservation_key=reservation_key,
                    )
                    self.db.commit()
                except Exception:
                    self.db.rollback()
            logger.exception("Failed to persist harness model usage: runtime_run=%s", self.runtime_run.id)

    def _mark_active_reservations_uncertain(self) -> None:
        if not self._active_reservation_keys:
            return
        keys = tuple(self._active_reservation_keys)
        self._active_reservation_keys.clear()
        try:
            for reservation_key in keys:
                mark_model_reservation_uncertain(
                    self.db,
                    org_id=self.user.org_id,
                    reservation_key=reservation_key,
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("Failed to mark harness reservations uncertain: runtime_run=%s", self.runtime_run.id)


async def stream_harness_assistant_response(
    db: Session,
    user: CurrentUser,
    *,
    run: RuntimeRun,
    conversation_id: str,
    llm: Any,
    provider_type: str,
    provider_source: ProviderSource,
    model: str | None,
    user_message: str,
    conversation_context: list[dict[str, str]] | None = None,
    conversation_summary: str = "",
    conversation_history_truncated: bool = False,
    conversation_window: ConversationContextWindow | None = None,
    memory_context_records: list[dict[str, Any]] | None = None,
    memory_context_version: str | None = None,
    available_attachments: list[dict[str, Any]] | None = None,
    attachment_context: str = "",
    active_project_id: str | None = None,
    pending_input: dict[str, Any] | None = None,
    approval_mode: str = "risky_only",
    provider_config_id: str | None = None,
    reasoning_effort: str | None = None,
    after_sequence: int = 0,
) -> AsyncGenerator[str, None]:
    harness = StreamingHarness(
        db=db,
        user=user,
        run=run,
        conversation_id=conversation_id,
        llm=llm,
        provider_type=provider_type,
        provider_source=provider_source,
        model=model,
        user_message=user_message,
        conversation_context=conversation_context,
        conversation_summary=conversation_summary,
        conversation_history_truncated=conversation_history_truncated,
        conversation_window=conversation_window,
        memory_context_records=memory_context_records,
        memory_context_version=memory_context_version,
        available_attachments=available_attachments,
        attachment_context=attachment_context,
        active_project_id=active_project_id,
        pending_input=pending_input,
        approval_mode=approval_mode,
        provider_config_id=provider_config_id,
        reasoning_effort=reasoning_effort,
        after_sequence=after_sequence,
    )
    async for event in harness.run():
        yield event
