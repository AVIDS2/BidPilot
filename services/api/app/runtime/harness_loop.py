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

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from sqlalchemy.orm import Session

from app.assistant.audit import redact_arguments, redact_text
from app.auth.schemas import CurrentUser
from app.chat.service import bind_conversation_project_context, save_message
from app.models import RuntimeRun
from app.usage.schemas import ProviderSource
from app.usage.service import UsageLimitExceeded, reserve_assistant_model_tokens
from contracts.model_usage import ProviderUsageMeasurement, normalize_langchain_usage
from contracts.untrusted_context import build_untrusted_context_packet, with_untrusted_context_guard
from contracts.usage_ledger import (
    mark_model_reservation_uncertain,
    record_model_usage,
    release_model_reservation,
    settle_model_reservation,
)

from .model_limits import (
    OPERATOR_PLANNER_MAX_ATTACHMENT_CONTEXT_CHARACTERS,
    OPERATOR_PLANNER_MAX_CONVERSATION_CONTEXT_CHARACTERS,
    OPERATOR_PLANNER_MAX_MEMORY_CONTEXT_CHARACTERS,
    OPERATOR_PLANNER_MAX_PREVIOUS_RESULT_CHARACTERS,
    OPERATOR_PLANNER_MAX_USER_MESSAGE_CHARACTERS,
)
from .registry import (
    CAPABILITY_REGISTRY,
    PublicCapabilityResult,
    get_capability_definition,
    missing_required_capability_arguments,
)
from .service import (
    cancel_runtime_run,
    complete_runtime_run,
    execute_capability,
    fail_runtime_run,
    resolve_approval,
)
from contracts.runtime import RuntimeApprovalDecisionType

logger = logging.getLogger(__name__)

# Re-export for type checkers / tests without circular import noise.
ModelUsageObserver = Callable[[ProviderUsageMeasurement | None], None]

HARNESS_MAX_STEPS = 8
HARNESS_MAX_TOOLS_PER_TURN = 6
_LLM_TOOL_RESULT_MAX_CHARS = 2_000

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
            "decision": {"type": "string", "enum": ["approved", "rejected"]},
            "comment": {"type": "string"},
        },
        "required": ["project_id", "section_id", "decision"],
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
        "properties": {"project_id": {"type": "string"}, "query": {"type": "string"}},
        "required": ["project_id", "query"],
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
}


def build_capability_tool_specs() -> list[dict[str, Any]]:
    """OpenAI-compatible tool specs derived from the product capability registry."""
    tools: list[dict[str, Any]] = []
    for definition in sorted(CAPABILITY_REGISTRY.values(), key=lambda item: item.name):
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
        memory_context_records: list[dict[str, Any]] | None = None,
        available_attachments: list[dict[str, Any]] | None = None,
        active_project_id: str | None = None,
        pending_input: dict[str, Any] | None = None,
        provider_config_id: str | None = None,
        reasoning_effort: str | None = None,
        max_steps: int = HARNESS_MAX_STEPS,
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
        self.memory_context_records = memory_context_records or []
        self.available_attachments = available_attachments or []
        self.active_project_id = active_project_id
        self.pending_input = pending_input or {}
        self.provider_config_id = provider_config_id
        self.reasoning_effort = reasoning_effort
        self.max_steps = max(1, max_steps)
        self.after_sequence = after_sequence
        self._active_reservation_keys: list[str] = []
        self._cursor = after_sequence
        self._streamed_text = False
        self._consecutive_tool_failures = 0

    async def run(self) -> AsyncGenerator[str, None]:
        messages = self._initial_messages()
        tools = build_capability_tool_specs()
        bound = self.llm.bind_tools(tools)

        try:
            for step in range(self.max_steps):
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

                if not tool_calls:
                    final_text = "".join(text_parts).strip() or "我可以继续帮你处理这个请求。"
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

                # Keep the assistant message that requested tools in the transcript.
                ai_tool_message = AIMessage(
                    content="".join(text_parts),
                    tool_calls=[
                        {
                            "id": item.tool_call_id,
                            "name": item.name,
                            "args": item.arguments,
                        }
                        for item in tool_calls[:HARNESS_MAX_TOOLS_PER_TURN]
                    ],
                )
                messages.append(ai_tool_message)

                executed_names: list[str] = []
                for item in tool_calls[:HARNESS_MAX_TOOLS_PER_TURN]:
                    async for event in self._execute_one_tool(item, turn_id, messages, executed_names):
                        yield event
                        # Approval pause ends the current stream; client resumes later.
                        if event.startswith("event: assistant.confirmation_requested") or (
                            event.startswith("event: assistant.end") and "needs_confirmation" in event
                        ):
                            return
                        # Hard stop after consecutive tool failures.
                        if event.startswith("event: assistant.end") and '"state": "failed"' in event:
                            return

                summary = build_turn_summary(executed_names)
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
            safe_error = redact_text(str(exc))
            message = f"执行失败：{safe_error}"
            try:
                fail_runtime_run(self.db, self.runtime_run.id, message, error_code="harness_loop_failed")
            except ValueError:
                pass
            save_message(self.db, self.conversation_id, "assistant", message)
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
        """Resume a paused approval and optionally continue the harness."""
        try:
            if not approved:
                from contracts.runtime import RuntimeApprovalDecisionType as Decision

                resolve_approval(
                    self.db,
                    self.user,
                    approval_id=approval_id,
                    decision=Decision.REJECT,
                )
                message = "已取消这次操作。"
                cancel_runtime_run(self.db, self.runtime_run.id, message)
                save_message(self.db, self.conversation_id, "assistant", message)
                async for event in self._flush_new_events():
                    yield event
                return

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
            result = execution.result or PublicCapabilityResult("操作已完成。", {})
            self._maybe_bind_project(tool_name, result.payload)
            # Surface success immediately, then let a short continuation turn
            # summarize / offer next steps instead of hard-stopping the loop.
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
            async for event in self._flush_new_events(skip_message_completed=True):
                yield event
            yield _sse(
                "assistant.message",
                {
                    "runtime_run_id": self.runtime_run.id,
                    "content": result.summary,
                    "state": "completed",
                },
            )
            yield _sse(
                "assistant.end",
                {
                    "conversation_id": self.conversation_id,
                    "runtime_run_id": self.runtime_run.id,
                    "state": "completed",
                },
            )
        except Exception as exc:
            safe_error = redact_text(str(exc))
            message = f"执行失败：{safe_error}"
            # Keep the failure visible as a tool card, but do not strand the UI
            # without a clear next step. Typed confirmation mismatches should
            # tell the user exactly what to type, not look like a fake sandbox.
            yield _sse(
                "assistant.tool_failed",
                {
                    "runtime_run_id": self.runtime_run.id,
                    "tool_name": tool_name,
                    "error_message": safe_error,
                    "state": "failed",
                },
            )
            try:
                fail_runtime_run(self.db, self.runtime_run.id, message, error_code="harness_approval_failed")
            except ValueError:
                pass
            guidance = message
            if "完整项目名称" in safe_error or "confirmation" in safe_error.lower():
                guidance = (
                    f"{message}\n\n"
                    "这不是沙箱假失败：删除属于破坏性操作，即使在「完全访问」下也需要输入完整项目名称确认。"
                    "请再次发起删除，并在确认框中输入完整项目名。"
                )
            save_message(self.db, self.conversation_id, "assistant", guidance)
            async for event in self._flush_new_events(skip_message_completed=True):
                yield event
            yield _sse(
                "assistant.message",
                {
                    "runtime_run_id": self.runtime_run.id,
                    "content": guidance,
                    "state": "failed",
                },
            )
            yield _sse(
                "assistant.end",
                {
                    "conversation_id": self.conversation_id,
                    "runtime_run_id": self.runtime_run.id,
                    "state": "failed",
                },
            )

    def _initial_messages(self) -> list[Any]:
        capability_list = "、".join(
            f"{item.name}（{item.label_zh}）"
            for item in sorted(CAPABILITY_REGISTRY.values(), key=lambda value: value.name)
        )
        system = with_untrusted_context_guard(
            "你是 BidPilot 的平台执行助手。你可以回答问题，也可以调用注册工具。\n"
            "规则：\n"
            "1. 只使用提供的工具；禁止虚构执行结果。\n"
            "2. 信息不足时先用中文追问一个最关键字段，不要瞎猜 ID。\n"
            "3. 变更类操作由服务端审批，你仍然可以提出 tool call。\n"
            "4. 若 active_project_id 存在，项目范围内操作优先使用它。\n"
            "5. 工具结果返回后，用简洁中文总结并推进下一步。\n"
            "6. 写作/起草任务：先 get_project_outline 或 list_sections 拿到 section_key，"
            "再 start_draft_section 或 write_section；禁止只在聊天里写长文代替章节写入。"
            "用户说「自行完成/拟草」时：无资料用 write_section 直接写入；有资料用 start_draft_section。\n"
            "7. outline/sections 工具结果里的 sections[].section_key 必须原样用于后续工具，"
            "不要声称「没有 section_key」。\n"
            "8. search_projects 结果若存在同名项目，必须用 projects[].id 或 short_id 区分；"
            "禁止发明「(1)/(2)」标签；删除/打开前先复述目标 id。\n"
            "9. 若上一轮已进入待确认删除/写入，优先等待用户确认，不要重复搜索或重新发起同类操作。\n"
            f"可用工具：{capability_list}"
        )
        packet = build_untrusted_context_packet(
            "harness_planning",
            (
                {
                    "user_message": self.user_message[:OPERATOR_PLANNER_MAX_USER_MESSAGE_CHARACTERS],
                    "conversation_context_json": json.dumps(self.conversation_context, ensure_ascii=False)[
                        :OPERATOR_PLANNER_MAX_CONVERSATION_CONTEXT_CHARACTERS
                    ],
                    "active_project_id": self.active_project_id,
                    "pending_input_json": json.dumps(self.pending_input, ensure_ascii=False)[
                        :OPERATOR_PLANNER_MAX_PREVIOUS_RESULT_CHARACTERS
                    ],
                    "available_attachments_json": json.dumps(self.available_attachments, ensure_ascii=False)[
                        :OPERATOR_PLANNER_MAX_ATTACHMENT_CONTEXT_CHARACTERS
                    ],
                    "long_term_memory_json": json.dumps(self.memory_context_records, ensure_ascii=False)[
                        :OPERATOR_PLANNER_MAX_MEMORY_CONTEXT_CHARACTERS
                    ],
                },
            ),
        )
        messages: list[Any] = [SystemMessage(content=system)]
        for item in self.conversation_context:
            role = item.get("role")
            content = (item.get("content") or "").strip()
            if not content:
                continue
            if role == "assistant":
                messages.append(AIMessage(content=content))
            else:
                messages.append(HumanMessage(content=content))
        messages.append(
            HumanMessage(
                content=(
                    "Use tools when a platform action is needed. "
                    "Attachment IDs may be selected only from the listed staged attachments.\n\n"
                    f"UNTRUSTED_CONTEXT_JSON:\n{packet}"
                )
            )
        )
        return messages

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
                args = tc.get("args") if isinstance(tc.get("args"), dict) else {}
                tool_call_id = str(tc.get("id") or f"call_{uuid4().hex[:12]}")
            else:
                name = str(getattr(tc, "name", "") or "")
                raw_args = getattr(tc, "args", {}) or {}
                args = raw_args if isinstance(raw_args, dict) else {}
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

        missing = ()
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
            tool_payload = {"error": message, "missing_fields": list(missing)}
            messages.append(
                ToolMessage(
                    content=json.dumps(tool_payload, ensure_ascii=False)[:_LLM_TOOL_RESULT_MAX_CHARS],
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
                    "error_message": message,
                    "state": "failed",
                },
            )
            return

        action_key = f"harness:{turn_id}:{item.tool_call_id}:{item.name}"
        try:
            definition = get_capability_definition(item.name)
        except ValueError:
            message = f"未知工具：{item.name}"
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
                    "error_message": message,
                    "state": "failed",
                },
            )
            return

        # Emit a started event early for live UI even before durable capability.started.
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
            safe_error = redact_text(str(exc))
            self._consecutive_tool_failures += 1
            messages.append(
                ToolMessage(
                    content=json.dumps({"error": safe_error}, ensure_ascii=False)[:_LLM_TOOL_RESULT_MAX_CHARS],
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
                    "error_message": safe_error,
                    "state": "failed",
                },
            )
            async for event in self._flush_new_events():
                yield event
            if self._consecutive_tool_failures >= 3:
                stop = "连续多次工具执行失败，我先停在这里。请换一种说法或检查项目上下文后再试。"
                save_message(self.db, self.conversation_id, "assistant", stop)
                try:
                    fail_runtime_run(self.db, self.runtime_run.id, stop, error_code="harness_tool_failures")
                except ValueError:
                    pass
                async for event in self._flush_new_events(skip_message_completed=True):
                    yield event
                yield _sse(
                    "assistant.end",
                    {
                        "conversation_id": self.conversation_id,
                        "runtime_run_id": self.runtime_run.id,
                        "state": "failed",
                    },
                )
            return

        if execution.approval is not None:
            async for event in self._flush_new_events():
                yield event
            yield _sse(
                "assistant.end",
                {
                    "conversation_id": self.conversation_id,
                    "runtime_run_id": self.runtime_run.id,
                    "state": "needs_confirmation",
                },
            )
            return

        if execution.action.status == "denied":
            message = execution.action.error_message or "操作被拒绝。"
            messages.append(
                ToolMessage(
                    content=json.dumps({"error": message}, ensure_ascii=False)[:_LLM_TOOL_RESULT_MAX_CHARS],
                    tool_call_id=item.tool_call_id,
                )
            )
            async for event in self._flush_new_events():
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
        async for event in self._flush_new_events():
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

    async def _flush_new_events(
        self,
        *,
        skip_message_completed: bool = False,
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
            for rendered in _render_runtime_event(event, self.conversation_id):
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
    memory_context_records: list[dict[str, Any]] | None = None,
    available_attachments: list[dict[str, Any]] | None = None,
    active_project_id: str | None = None,
    pending_input: dict[str, Any] | None = None,
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
        memory_context_records=memory_context_records,
        available_attachments=available_attachments,
        active_project_id=active_project_id,
        pending_input=pending_input,
        provider_config_id=provider_config_id,
        reasoning_effort=reasoning_effort,
        after_sequence=after_sequence,
    )
    async for event in harness.run():
        yield event
