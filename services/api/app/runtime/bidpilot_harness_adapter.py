"""Governed BidPilot tool adapter for the framework-neutral harness core.

The generic loop never receives a database session, a user, or a capability
name.  This adapter is the only bridge from a model tool call to the existing
runtime action lifecycle.  It deliberately has no model-loop or SSE logic.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.assistant.task_state import clear_task_state, set_task_state
from app.assistant.audit import redact_arguments
from app.auth.schemas import CurrentUser
from app.chat.service import bind_conversation_project_context
from app.db import SessionLocal
from app.models import RuntimeRun

from .events import RuntimeEventDraft, publish_event
from .failures import classify_capability_failure
from .harness_core import (
    HarnessExecutionContext,
    HarnessToolCall,
    HarnessToolOutcome,
)
from .registry import (
    CAPABILITY_REGISTRY,
    PublicCapabilityResult,
    get_capability_definition,
    missing_required_capability_arguments,
)
from .service import execute_prepared_capability, prepare_capability_execution
from .skills import read_skill
from contracts.runtime import RuntimeEventType
from contracts.runtime import RuntimeRiskLevel


EXTERNAL_IO_CAPABILITIES = frozenset(
    {"web_search", "discover_remote_documents", "fetch_url_to_project"}
)
MODEL_PROVIDER_CAPABILITIES = frozenset(
    {"start_draft_section", "start_redraft_section", "propose_memory_graph"}
)


@dataclass(frozen=True)
class _PreparedCapability:
    action_id: str
    capability_name: str
    mutation_key: tuple[str, str] | None = None


@dataclass(frozen=True)
class _PreparedMcpTool:
    server_name: str
    tool_name: str
    public_tool_name: str
    title: str


@dataclass(frozen=True)
class _PreparedSkill:
    name: str
    body: str


class BidPilotToolExecutor:
    """Translate core tool calls into one governed RuntimeAction each.

    ``prepare`` is intentionally separate from ``execute``.  The service
    commits ``capability.started`` while creating the action; only then does
    the core loop emit ``tool.started`` and allow a side effect.  A reconnect
    therefore sees the exact action it is about to execute, and an identical
    call key is replayed instead of run twice.
    """

    allow_parallel_tools = True
    allow_parallel_prepared_tools = True

    def __init__(
        self,
        *,
        db: Session,
        user: CurrentUser,
        runtime_run: RuntimeRun,
        conversation_id: str,
        parameter_schemas: Mapping[str, Mapping[str, Any]],
        allowed_capabilities: frozenset[str] | None = None,
        active_project_id: str | None = None,
        provider_config_id: str | None = None,
        reasoning_effort: str | None = None,
        on_project_bound: Callable[[str], None] | None = None,
        parent_event_id_provider: Callable[[], str | None] | None = None,
        preflight_guard: Callable[[HarnessToolCall], str | None] | None = None,
    ) -> None:
        self.db = db
        self.user = user
        self.runtime_run = runtime_run
        self.conversation_id = conversation_id
        self.parameter_schemas = parameter_schemas
        self.allowed_capabilities = allowed_capabilities or frozenset(CAPABILITY_REGISTRY)
        self.active_project_id = active_project_id
        self.provider_config_id = provider_config_id
        self.reasoning_effort = reasoning_effort
        self.on_project_bound = on_project_bound
        self.parent_event_id_provider = parent_event_id_provider
        self.preflight_guard = preflight_guard
        self._prepared: dict[str, _PreparedCapability | _PreparedMcpTool] = {}
        self._successful_mutations: dict[tuple[str, str], HarnessToolOutcome] = {}

    async def prepare(
        self,
        call: HarnessToolCall,
        context: HarnessExecutionContext,
    ) -> HarnessToolOutcome | None:
        """Validate/persist an action before the core loop permits execution."""
        if self.preflight_guard is not None:
            try:
                blocked_reason = self.preflight_guard(call)
            except Exception:  # noqa: BLE001 - policy hooks cannot break the harness
                blocked_reason = "安全策略暂时不可用。"
            if blocked_reason is not None:
                return HarnessToolOutcome.blocked(
                    "该工具请求被当前安全策略阻止。",
                    error_code="capability_policy_blocked",
                )
        if call.name == "read_skill":
            name = str(call.arguments.get("name") or "").strip()
            body = read_skill(name)
            if not body:
                return HarnessToolOutcome.failed(
                    "未找到该流程技能，请使用 AVAILABLE_SKILLS 中的准确名称。",
                    error_code="skill_not_found",
                    recoverable=True,
                )
            self._prepared[call.id] = _PreparedSkill(name=name, body=body)
            return None

        mcp_route = self._mcp_route(call.name)
        if mcp_route is not None:
            server_name, tool_name, public_tool_name, title = mcp_route
            self._prepared[call.id] = _PreparedMcpTool(
                server_name=server_name,
                tool_name=tool_name,
                public_tool_name=public_tool_name,
                title=title,
            )
            publish_event(
                self.db,
                self.runtime_run.id,
                RuntimeEventDraft(
                    type=RuntimeEventType.CAPABILITY_STARTED,
                    parent_event_id=(self.parent_event_id_provider() if self.parent_event_id_provider else None),
                    public_summary=f"正在{title}。",
                    payload={
                        "capability": public_tool_name,
                        "title": title,
                        "tool_call_id": call.id,
                        "turn_id": context.turn_id,
                        "provider": f"mcp:{server_name}",
                    },
                ),
            )
            return None
        if call.name not in self.allowed_capabilities:
            return HarnessToolOutcome.blocked(
                "请求了不可用的工具，请调整操作目标后重试。",
                error_code="capability_unavailable",
            )
        try:
            definition = get_capability_definition(call.name)
        except ValueError:
            return HarnessToolOutcome.blocked(
                "请求了不可用的工具，请调整操作目标后重试。",
                error_code="capability_unavailable",
            )

        arguments = self._normalize_arguments(call.name, call.arguments)
        try:
            missing = missing_required_capability_arguments(call.name, arguments)
        except Exception:
            missing = ()
        if missing:
            message = (
                "请告诉我项目名称。"
                if call.name == "create_project" and missing == ("name",)
                else f"还需要补充：{'、'.join(missing)}"
            )
            set_task_state(
                self.db,
                self.conversation_id,
                status="needs_input",
                tool_name=call.name,
                arguments=arguments,
                missing_fields=missing,
            )
            publish_event(
                self.db,
                self.runtime_run.id,
                RuntimeEventDraft(
                    type=RuntimeEventType.PLAN_UPDATED,
                    public_summary=message,
                    payload={
                        "stage": "needs_input",
                        "mode": "needs_input",
                        "turn_id": context.turn_id,
                        "tool_call_id": call.id,
                        "capability": call.name,
                        "missing_fields": list(missing),
                    },
                ),
            )
            return HarnessToolOutcome.paused(
                message,
                pause_reason="needs_input",
                model_payload={"missing_fields": list(missing), "capability": call.name},
            )

        mutation_key = self._mutation_key(definition, call.name, arguments)
        if mutation_key is not None:
            previous = self._successful_mutations.get(mutation_key)
            if previous is not None:
                return HarnessToolOutcome.succeeded(
                    "该写入操作已在本次运行中完成，未重复执行。",
                    previous.model_payload,
                )

        action_key = f"core:{self.runtime_run.id}:{context.turn_id}:{call.id}:{call.name}"
        try:
            execution = prepare_capability_execution(
                self.db,
                self.user,
                run_id=self.runtime_run.id,
                capability_name=call.name,
                arguments=arguments,
                action_key=action_key,
                parent_event_id=(self.parent_event_id_provider() if self.parent_event_id_provider else None),
                turn_id=context.turn_id,
            )
        except Exception as exc:  # noqa: BLE001 - only public failure crosses the port
            failure = classify_capability_failure(exc)
            self._publish_preflight_failure(
                capability_name=call.name,
                turn_id=context.turn_id,
                tool_call_id=call.id,
                message=failure.message,
                reason_code=failure.error_code,
            )
            return HarnessToolOutcome.failed(
                failure.message,
                error_code=failure.error_code,
                recoverable=True,
            )

        if execution.approval is not None:
            return HarnessToolOutcome.paused(
                "该操作需要你的确认。",
                pause_reason="needs_approval",
                model_payload={"approval_id": execution.approval.id, "capability": call.name},
            )
        if execution.action.status == "denied":
            return HarnessToolOutcome.blocked(
                execution.action.error_message or "操作被当前策略拒绝。",
                error_code=execution.action.error_code or "capability_denied",
            )

        self._prepared[call.id] = _PreparedCapability(
            action_id=execution.action.id,
            capability_name=definition.name,
            mutation_key=mutation_key,
        )
        return None

    def can_prepare_parallel(self, calls: Sequence[HarnessToolCall]) -> bool:
        """Restrict fan-out to read-only MCP sensing tools.

        Product capabilities always create a RuntimeAction and may require
        approval, so their ordering is intentionally preserved. MCP calls are
        separately namespaced and sensing-only by default; their preflight is
        local bookkeeping rather than a business mutation.
        """
        return bool(calls) and all(self._mcp_route(call.name) is not None for call in calls)

    async def execute(
        self,
        call: HarnessToolCall,
        _context: HarnessExecutionContext,
    ) -> HarnessToolOutcome:
        prepared = self._prepared.pop(call.id, None)
        if prepared is None:
            return HarnessToolOutcome.failed(
                "工具执行前置状态丢失，请重试。",
                error_code="tool_preparation_missing",
                recoverable=True,
            )
        if isinstance(prepared, _PreparedMcpTool):
            return await self._execute_mcp(call, prepared, _context)
        if isinstance(prepared, _PreparedSkill):
            return HarnessToolOutcome.succeeded(
                f"已加载流程技能：{prepared.name}。",
                {
                    "status": "loaded",
                    "skill_name": prepared.name,
                    "instructions": prepared.body,
                },
                public_payload={"skill_name": prepared.name},
            )
        try:
            if prepared.capability_name in EXTERNAL_IO_CAPABILITIES:
                execution = await asyncio.to_thread(
                    _execute_prepared_in_worker,
                    self.user,
                    prepared.action_id,
                )
                self.db.expire_all()
            else:
                execution = execute_prepared_capability(
                    self.db,
                    self.user,
                    action_id=prepared.action_id,
                )
        except Exception as exc:  # noqa: BLE001 - classified at a public boundary
            failure = classify_capability_failure(exc)
            return HarnessToolOutcome.failed(
                self._failure_message(prepared.capability_name, failure.message),
                error_code=failure.error_code,
                recoverable=self._is_auto_retry_safe(prepared.capability_name, failure.error_code),
            )

        if execution.approval is not None:
            return HarnessToolOutcome.paused(
                "该操作需要你的确认。",
                pause_reason="needs_approval",
                model_payload={"approval_id": execution.approval.id, "capability": prepared.capability_name},
            )
        if execution.action.status == "denied":
            return HarnessToolOutcome.blocked(
                execution.action.error_message or "操作被当前策略拒绝。",
                error_code=execution.action.error_code or "capability_denied",
            )
        if execution.action.status != "succeeded":
            return HarnessToolOutcome.failed(
                self._failure_message(
                    prepared.capability_name,
                    execution.action.error_message or "工具未能完成。",
                ),
                error_code=execution.action.error_code or "capability_execution_failed",
                recoverable=self._is_auto_retry_safe(
                    prepared.capability_name,
                    execution.action.error_code or "capability_execution_failed",
                ),
            )

        result = execution.result or PublicCapabilityResult("操作已完成。", {})
        if callable(getattr(self.db, "get", None)):
            clear_task_state(self.db, self.conversation_id)
        self._bind_created_project(prepared.capability_name, result.payload)
        outcome = HarnessToolOutcome.succeeded(
            result.summary,
            result.observation_payload or result.payload,
            public_payload=result.payload,
        )
        if prepared.mutation_key is not None:
            self._successful_mutations[prepared.mutation_key] = outcome
        return outcome

    async def _execute_mcp(
        self,
        call: HarnessToolCall,
        prepared: _PreparedMcpTool,
        context: HarnessExecutionContext,
    ) -> HarnessToolOutcome:
        """Execute an optional sensing extension through the core tool contract.

        MCP is intentionally not a RuntimeAction: it has no platform mutation
        and can be unavailable between discovery and a later tool call.  Its
        own started/succeeded/failed events are nevertheless durable so a
        reconnect never loses the source that informed a model response.
        """
        try:
            from .mcp_client import call_mcp_tool

            outcome = await call_mcp_tool(prepared.server_name, prepared.tool_name, dict(call.arguments))
        except Exception:  # noqa: BLE001 - external details must stay private
            message = "联网搜索服务暂时不可用，请稍后重试。" if prepared.public_tool_name == "web_search" else "扩展工具暂时不可用，请稍后重试。"
            self._publish_mcp_result(
                prepared,
                context=context,
                tool_call_id=call.id,
                event_type=RuntimeEventType.CAPABILITY_FAILED,
                summary=message,
                payload={"reason_code": "mcp_unavailable"},
            )
            return HarnessToolOutcome.failed(
                message,
                error_code="mcp_unavailable",
                recoverable=True,
                # The model needs a machine-readable reason in order to choose
                # a fallback or ask the user to retry. The browser only gets
                # the short public message above.
                model_payload={
                    "provider": f"mcp:{prepared.server_name}",
                    "error_code": "mcp_unavailable",
                    "retryable": True,
                },
                public_payload={"reason_code": "mcp_unavailable"},
            )

        payload = self._mcp_public_payload(outcome, call.arguments, prepared)
        model_observation = self._mcp_model_observation(outcome, call.arguments, prepared)
        # Search candidates are already normalized to a small public-safe
        # schema. Surface them at the top level for the model as well: the
        # next turn can select a source without parsing an arbitrary MCP blob.
        if prepared.public_tool_name == "web_search":
            for key in ("query", "count", "items"):
                value = payload.get(key)
                if value is not None:
                    model_observation[key] = value
        summary = (
            "已获得可追溯的公开来源，正在核对关键信息。"
            if prepared.public_tool_name == "web_search"
            else f"{prepared.title}已完成。"
        )
        self._publish_mcp_result(
            prepared,
            context=context,
            tool_call_id=call.id,
            event_type=RuntimeEventType.CAPABILITY_SUCCEEDED,
            summary=summary,
            payload=payload,
        )
        return HarnessToolOutcome.succeeded(
            summary,
            model_observation,
            public_payload=payload,
        )

    @staticmethod
    def _mcp_route(name: str) -> tuple[str, str, str, str] | None:
        from .mcp_client import parse_mcp_tool_name

        route = parse_mcp_tool_name(name)
        if route is None:
            return None
        server_name, tool_name = route
        public_tool_name = "web_search" if server_name.casefold() == "tavily" and "search" in tool_name.casefold() else name
        title = "联网搜索" if public_tool_name == "web_search" else f"MCP · {tool_name}"
        return server_name, tool_name, public_tool_name, title

    @staticmethod
    def _mcp_public_payload(
        outcome: Any,
        arguments: Mapping[str, Any],
        prepared: _PreparedMcpTool,
    ) -> dict[str, Any]:
        """Build the small, user-facing projection of an MCP result."""
        if not isinstance(outcome, Mapping):
            outcome = {}
        if prepared.public_tool_name == "web_search":
            from .harness_loop import _mcp_search_payload

            return _mcp_search_payload(dict(outcome), dict(arguments), prepared.server_name)
        content = outcome.get("content")
        structured = outcome.get("structured_content")
        payload: dict[str, Any] = {
            "provider": f"mcp:{prepared.server_name}",
            "untrusted": True,
        }
        if isinstance(structured, Mapping):
            payload["structured_content"] = dict(structured)
        elif isinstance(content, str) and content.strip():
            payload["content"] = content[:2_000]
        return payload

    @staticmethod
    def _mcp_model_observation(
        outcome: Any,
        arguments: Mapping[str, Any],
        prepared: _PreparedMcpTool,
    ) -> dict[str, Any]:
        """Return a bounded redacted MCP observation to the next model turn.

        MCP results are external and untrusted. The harness nevertheless needs
        the actual result, not the UI projection, so it can reason about empty
        searches, select an attachment, or recover from a malformed response.
        This boundary redacts secrets and hard-bounds the JSON before it ever
        reaches a provider context window.
        """
        raw = redact_arguments(outcome)
        try:
            encoded = json.dumps(raw, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            encoded = json.dumps({"value": "<unserializable MCP result>"})
            raw = {"value": "<unserializable MCP result>"}
        max_characters = 12_000
        result: Any = raw
        truncated = len(encoded) > max_characters
        if truncated:
            result = {
                "truncated": True,
                "preview": encoded[:max_characters],
                "original_characters": len(encoded),
            }
        return {
            "provider": f"mcp:{prepared.server_name}",
            "tool": prepared.tool_name,
            "untrusted": True,
            "request": redact_arguments(dict(arguments)),
            "result": result,
            "truncated": truncated,
        }

    def _publish_mcp_result(
        self,
        prepared: _PreparedMcpTool,
        *,
        context: HarnessExecutionContext,
        tool_call_id: str,
        event_type: RuntimeEventType,
        summary: str,
        payload: Mapping[str, Any],
    ) -> None:
        publish_event(
            self.db,
            self.runtime_run.id,
            RuntimeEventDraft(
                type=event_type,
                parent_event_id=(self.parent_event_id_provider() if self.parent_event_id_provider else None),
                public_summary=summary,
                payload={
                    "capability": prepared.public_tool_name,
                    "title": prepared.title,
                    "tool_call_id": tool_call_id,
                    "turn_id": context.turn_id,
                    **dict(payload),
                },
            ),
        )

    def _normalize_arguments(self, capability_name: str, raw_arguments: Mapping[str, Any]) -> dict[str, Any]:
        arguments = dict(raw_arguments)
        schema = self.parameter_schemas.get(capability_name, {})
        properties = schema.get("properties") if isinstance(schema, Mapping) else None
        if (
            self.active_project_id
            and not str(arguments.get("project_id") or "").strip()
            and isinstance(properties, Mapping)
            and "project_id" in properties
        ):
            arguments["project_id"] = self.active_project_id
        if capability_name in MODEL_PROVIDER_CAPABILITIES:
            if self.provider_config_id and not arguments.get("provider_config_id"):
                arguments["provider_config_id"] = self.provider_config_id
            if self.reasoning_effort and not arguments.get("reasoning_effort"):
                arguments["reasoning_effort"] = self.reasoning_effort
        return arguments

    @staticmethod
    def _mutation_key(
        definition: Any,
        capability_name: str,
        arguments: Mapping[str, Any],
    ) -> tuple[str, str] | None:
        """Collapse an identical successful write within one active run.

        RuntimeAction action keys are intentionally unique per model call, so
        they cannot protect against a model retry with a new call id after a
        side effect committed but its result was lost. This in-memory guard is
        scoped to one harness invocation and only applies to governed writes.
        Durable replay remains the responsibility of RuntimeAction.
        """
        if getattr(definition, "risk_level", None) not in {
            RuntimeRiskLevel.LOW_RISK_WRITE,
            RuntimeRiskLevel.COSTING,
            RuntimeRiskLevel.DESTRUCTIVE,
        }:
            return None
        try:
            normalized = json.dumps(dict(arguments), ensure_ascii=False, sort_keys=True, default=str)
        except (TypeError, ValueError):
            return None
        return capability_name, normalized

    def _bind_created_project(self, capability_name: str, payload: Mapping[str, Any]) -> None:
        if capability_name not in {"create_project", "create_demo_workspace"}:
            return
        project_id = payload.get("id")
        if not isinstance(project_id, str) or not project_id:
            return
        bind_conversation_project_context(
            self.db,
            conversation_id=self.conversation_id,
            user_id=self.user.id,
            project_id=project_id,
        )
        self.active_project_id = project_id
        if self.on_project_bound is not None:
            self.on_project_bound(project_id)

    @staticmethod
    def _is_auto_retry_safe(capability_name: str, error_code: str) -> bool:
        """Keep a confirmed remote import as one explicit, inspectable attempt.

        A download may fail because the origin rejects a request, redirects to
        a login page, or changes a signed URL.  A model cannot safely repair
        any of those conditions by guessing a variant of the address.  The
        user can still start a new, deliberately confirmed attempt later.
        """
        if capability_name == "fetch_url_to_project":
            return False
        if error_code in {
            "project_limit_exceeded",
            "capability_input_invalid",
            "capability_forbidden",
            "capability_conflict",
            "capability_resource_not_found",
        }:
            return False
        return not error_code.startswith("authorization_")

    @staticmethod
    def _failure_message(capability_name: str, message: str) -> str:
        if capability_name != "fetch_url_to_project":
            return message
        return (
            f"{message} 已停止自动重试，未改写链接也未重复下载。"
            "你可以稍后重试、提供新的公开直链，或先手动下载后上传。"
        )

    def _publish_preflight_failure(
        self,
        *,
        capability_name: str,
        turn_id: str,
        tool_call_id: str,
        message: str,
        reason_code: str,
    ) -> None:
        publish_event(
            self.db,
            self.runtime_run.id,
            RuntimeEventDraft(
                type=RuntimeEventType.CAPABILITY_FAILED,
                public_summary=message,
                payload={
                    "capability": capability_name,
                    "turn_id": turn_id,
                    "tool_call_id": tool_call_id,
                    "reason_code": reason_code,
                },
            ),
        )


def _execute_prepared_in_worker(user: CurrentUser, action_id: str) -> Any:
    """Keep remote I/O off the async SSE loop using a short-lived session."""
    db = SessionLocal()
    try:
        return execute_prepared_capability(db, user, action_id=action_id)
    finally:
        db.close()


__all__ = ["BidPilotToolExecutor", "EXTERNAL_IO_CAPABILITIES"]
