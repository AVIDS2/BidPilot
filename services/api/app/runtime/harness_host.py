"""BidPilot host that projects the generic Pi-style loop onto Runtime/SSE.

``harness_core`` owns only model -> tools -> model.  This module owns the
product-specific edges: LangChain messages, RuntimeEvent projection, token
usage, and the governed capability adapter.  Keeping it separate from the
loop makes a non-BidPilot harness testable without an HTTP server or database.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator, Mapping, Sequence
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from app.agent.llm import get_required_tool_choice_llm
from app.chat.service import save_message
from contracts.runtime import RuntimeEventType

from .bidpilot_harness_adapter import BidPilotToolExecutor
from .events import RuntimeEventDraft, publish_event
from .harness_core import (
    HarnessEvent,
    HarnessExecutionContext,
    HarnessLoop,
    HarnessLoopConfig,
    HarnessMessage,
    HarnessModelFailure,
    HarnessModelStep,
    HarnessPlanPolicy,
    HarnessPlanUpdate,
    HarnessTerminalState,
    HarnessToolCall,
    HarnessToolDefinition,
    new_tool_call_id,
)
from .registry import get_capability_definition
from .harness_loop import (
    HARNESS_MAX_CONSECUTIVE_TOOL_FAILURES,
    StreamingHarness,
    _TOOL_PARAMETER_SCHEMAS,
    _extract_public_text_content,
    _sse,
    build_capability_tool_specs,
    build_public_reasoning,
    build_turn_summary,
    resolve_harness_budgets,
)
from .service import (
    complete_runtime_run,
    fail_runtime_run,
    finalize_requested_runtime_cancellation,
    runtime_cancellation_requested,
)


_REQUIRED_TOOL_CALL_CORRECTION = """
服务端拒绝了上一回合的纯文本确认，因为它没有产生任何工具调用。
本轮用户请求已经明确要求执行一个业务动作。现在必须从已注册工具中选择唯一合适的工具并返回工具调用，参数必须来自用户请求和当前上下文。
不要输出确认问题、计划说明或普通自然语言；不要假装已经执行。高风险操作会由服务端审批层暂停，缺少字段时由工具结果返回待补充信息。
""".strip()

_ACTION_MARKERS = (
    "创建",
    "新建",
    "生成",
    "起草",
    "导入",
    "下载",
    "上传",
    "删除",
    "更新",
    "运行",
    "执行",
    "发起",
    "审核",
    "提交",
    "导出",
    "入库",
    "同步",
    "发送",
    "create",
    "download",
    "upload",
    "run",
    "execute",
)
_CONFIRMATION_MARKERS = ("请确认", "请您确认", "确认", "确认后", "确认执行", "确认把", "将调用", "会调用", "调用接口")
_NEGATION_MARKERS = (
    "不要执行",
    "别执行",
    "不执行",
    "不要创建",
    "别创建",
    "不创建",
    "不要生成",
    "不要写入",
    "不写入",
    "仅解释",
    "只解释",
    "仅查询",
    "只查询",
    "不要修改",
    "不修改",
    "什么是",
    "能否说明",
)


def _requires_tool_call_correction(user_message: str, model_text: str) -> bool:
    """Detect a model's explicit promise to act without a protocol tool call."""
    user = user_message.strip().lower()
    text = model_text.strip().lower()
    explicit_action_request = any(marker in user for marker in _ACTION_MARKERS)
    clarification_only = any(marker in user for marker in _NEGATION_MARKERS) and not any(
        marker in user for marker in ("不要只解释", "不要仅解释", "不要只说明")
    )
    if not user or not text or (clarification_only and not explicit_action_request):
        return False
    return bool(
        any(marker.lower() in user for marker in _ACTION_MARKERS)
        and any(marker.lower() in text for marker in _CONFIRMATION_MARKERS)
        and ("调用" in text or "执行" in text or "入库" in text or "创建" in text)
    )


def _build_required_tool_bound(llm: Any, provider_specs: Sequence[dict[str, Any]]) -> Any | None:
    """Build the optional provider-specific required-tool retry binding."""
    try:
        action_llm = get_required_tool_choice_llm(llm)
        return action_llm.bind_tools(provider_specs, tool_choice="required")
    except (TypeError, ValueError):
        # Test doubles and providers without a compatible required-tool
        # contract continue on the normal binding; they never fail a turn at
        # startup merely because the recovery binding is unavailable.
        return None


class BidPilotHarnessPlanPolicy(HarnessPlanPolicy):
    """Project the loop's next tool calls into a small public execution plan.

    This is deliberately presentation-only.  RuntimeAction, approval and
    LangGraph execution records remain the source of truth for any mutation or
    long-running workflow.  The policy merely makes a model's already selected
    calls inspectable before the adapter begins executing them.
    """

    def update(
        self,
        *,
        messages: Sequence[HarnessMessage],
        calls: Sequence[HarnessToolCall],
        context: HarnessExecutionContext,
    ) -> HarnessPlanUpdate | None:
        _ = messages
        items: list[dict[str, Any]] = []
        labels: list[str] = []
        for call in calls:
            try:
                label = get_capability_definition(call.name).label_zh
            except ValueError:
                label = call.name
            labels.append(label)
            items.append(
                {
                    "id": call.id,
                    "capability": call.name,
                    "title": label,
                    "status": "planned",
                    "turn_id": context.turn_id,
                }
            )
        if not items:
            return None
        summary = f"执行计划：{'、'.join(labels)}。"
        return HarnessPlanUpdate(summary=summary, items=tuple(items))


class LangChainHarnessModelPort:
    """Map the core's portable transcript to the existing provider adapter."""

    def __init__(self, host: "CoreStreamingHarness", bound: Any, required_tool_bound: Any | None = None) -> None:
        self.host = host
        self.bound = bound
        self.required_tool_bound = required_tool_bound
        self.last_text = ""
        self.turn_id = "turn-1"
        self.step = 1
        self._required_tool_retry_used = False

    def begin_turn(self, *, turn_id: str, step: int) -> None:
        self.turn_id = turn_id
        self.step = step

    async def next_step(
        self,
        messages: Sequence[HarnessMessage],
        _tools: Sequence[HarnessToolDefinition],
    ) -> HarnessModelStep:
        text_parts: list[str] = []
        buffered_calls: list[Any] = []
        usage_holder: dict[str, Any] = {"measurement": None}
        try:
            self.host._reserve_model_capacity()
            await self.host._collect_model_step(
                self.bound,
                [
                    *_to_langchain_messages(messages),
                    HumanMessage(
                        content=self.host._trusted_runtime_status(
                            turn_id=self.turn_id,
                            step=self.step,
                        )
                    ),
                ],
                text_parts,
                buffered_calls,
                turn_id=self.turn_id,
                usage_holder=usage_holder,
            )
            self.host._observe_model_usage(usage_holder.get("measurement"))
        except Exception as exc:
            self.host._mark_active_reservations_uncertain()
            from app.usage.service import UsageLimitExceeded

            if isinstance(exc, UsageLimitExceeded):
                raise HarnessModelFailure(str(exc), error_code="usage_limit_exceeded") from exc
            raise
        self.last_text = "".join(text_parts)
        if (
            not buffered_calls
            and self.required_tool_bound is not None
            and not self._required_tool_retry_used
            and _requires_tool_call_correction(self.host.user_message, self.last_text)
        ):
            # A prose "please confirm" answer cannot create a durable
            # approval, action, or trace.  Let the model choose a tool in a
            # one-shot non-thinking retry; the governed adapter still owns
            # validation, authorization, and approval before any side effect.
            self._required_tool_retry_used = True
            text_parts.clear()
            buffered_calls.clear()
            retry_usage: dict[str, Any] = {"measurement": None}
            try:
                self.host._reserve_model_capacity()
                await self.host._collect_model_step(
                    self.required_tool_bound,
                    [
                        *_to_langchain_messages(messages),
                        SystemMessage(content=_REQUIRED_TOOL_CALL_CORRECTION),
                        HumanMessage(
                            content=self.host._trusted_runtime_status(
                                turn_id=self.turn_id,
                                step=self.step,
                            )
                        ),
                    ],
                    text_parts,
                    buffered_calls,
                    turn_id=self.turn_id,
                    usage_holder=retry_usage,
                )
                self.host._observe_model_usage(retry_usage.get("measurement"))
            except Exception:
                self.host._mark_active_reservations_uncertain()
                raise
            self.last_text = "".join(text_parts)
        return HarnessModelStep(
            text=self.last_text,
            tool_calls=tuple(
                HarnessToolCall(
                    id=item.tool_call_id or new_tool_call_id(),
                    name=item.name,
                    arguments=dict(item.arguments),
                )
                for item in buffered_calls
            ),
            usage=_usage_payload(usage_holder.get("measurement")),
        )


class CoreStreamingHarness(StreamingHarness):
    """Production Host for the generic loop.

    The legacy class remains available for narrowly scoped approval-resume and
    compatibility tests.  Normal public turns enter this subclass through
    ``stream_harness_assistant_response`` and are therefore executed by
    :class:`HarnessLoop`.
    """

    async def run(self) -> AsyncGenerator[str, None]:
        from .background_tasks import collect_completed_notifications
        from .hooks import HookContext, default_hook_registry, register_default_recovery_hooks

        register_default_recovery_hooks()
        notifications = collect_completed_notifications(
            self.db,
            conversation_id=self.conversation_id,
            user_id=self.user.id,
        )
        initial_messages = self._initial_messages(background_notifications=notifications)
        self._persist_context_trace()
        provider_specs = build_capability_tool_specs(allowed_names=self._allowed_capability_names)
        try:
            from .mcp_client import list_mcp_tool_specs

            provider_specs.extend(
                {
                    "type": "function",
                    "function": {
                        "name": spec.name,
                        "description": spec.description,
                        "parameters": spec.parameters,
                    },
                }
                for spec in await list_mcp_tool_specs()
            )
        except Exception:  # noqa: BLE001 - optional sensing extensions never block a turn
            pass
        tools = tuple(_to_core_tool_definition(spec) for spec in provider_specs)
        bound = self.llm.bind_tools(provider_specs)
        required_tool_bound = _build_required_tool_bound(self.llm, provider_specs)
        model = LangChainHarnessModelPort(self, bound, required_tool_bound)
        executor = BidPilotToolExecutor(
            db=self.db,
            user=self.user,
            runtime_run=self.runtime_run,
            conversation_id=self.conversation_id,
            parameter_schemas=_TOOL_PARAMETER_SCHEMAS,
            allowed_capabilities=self._allowed_capability_names,
            active_project_id=self.active_project_id,
            provider_config_id=self.provider_config_id,
            reasoning_effort=self.reasoning_effort,
            on_project_bound=self._set_active_project,
            parent_event_id_provider=lambda: self._active_turn_event_id,
            preflight_guard=lambda call: default_hook_registry.first_blocking(
                "PreToolUse",
                hook_context,
                tool_name=call.name,
                arguments=call.arguments,
            ),
        )
        configured_steps, configured_tools = resolve_harness_budgets(self.user_message)
        loop = HarnessLoop(
            run_id=self.runtime_run.id,
            model=model,
            executor=executor,
            tools=tools,
            config=HarnessLoopConfig(
                max_steps=max(1, self.max_steps or configured_steps),
                max_tools_per_turn=max(1, self.max_tools_per_turn or configured_tools),
                max_consecutive_failures=HARNESS_MAX_CONSECUTIVE_TOOL_FAILURES,
            ),
            cancellation_check=lambda: runtime_cancellation_requested(self.db, self.runtime_run.id),
            plan_policy=BidPilotHarnessPlanPolicy(),
        )
        hook_context = HookContext(
            conversation_id=self.conversation_id,
            runtime_run_id=self.runtime_run.id,
            user_id=self.user.id,
            project_id=self.active_project_id,
        )
        default_hook_registry.trigger("UserPromptSubmit", hook_context, self.user_message)
        try:
            async for event in loop.stream(_to_core_messages(initial_messages)):
                async for projected in self._project_core_event(event, model=model, hook_context=hook_context):
                    yield projected
        except GeneratorExit:
            raise
        except Exception as exc:  # noqa: BLE001 - classify only at public boundary
            self._mark_active_reservations_uncertain()
            failure = self._core_failure_message(exc)
            try:
                fail_runtime_run(
                    self.db,
                    self.runtime_run.id,
                    failure,
                    error_code="harness_host_failed",
                    parent_event_id=self._active_turn_event_id,
                )
            except ValueError:
                pass
            save_message(self.db, self.conversation_id, "assistant", failure)
            async for projected in self._flush_core_events():
                yield projected

    async def _project_core_event(
        self,
        event: HarnessEvent,
        *,
        model: LangChainHarnessModelPort,
        hook_context: Any,
    ) -> AsyncGenerator[str, None]:
        if event.type == "run.started":
            return
        if event.type == "turn.started":
            model.begin_turn(
                turn_id=event.turn_id or "turn-unknown",
                step=int(event.payload.get("step") or 1),
            )
            self._active_turn_event_id = self._publish_turn_started(
                turn_id=event.turn_id or "turn-unknown",
                step=int(event.payload.get("step") or 1),
            )
            if self._active_turn_event_id is not None:
                async for rendered in self._flush_core_events():
                    yield rendered
            else:
                yield _sse(
                    "assistant.turn_started",
                    {
                        "runtime_run_id": self.runtime_run.id,
                        "turn_id": event.turn_id,
                        "step": event.payload.get("step"),
                        "state": "thinking",
                    },
                )
            return
        if event.type == "turn.model_response":
            narration = build_public_reasoning(
                [],
                active_project_id=self.active_project_id,
                completed_capabilities=self._completed_capabilities,
                model_narration=model.last_text,
            )
            if narration:
                async for rendered in self._emit_public_reasoning(
                    turn_id=event.turn_id or "turn-unknown",
                    content=narration,
                ):
                    yield rendered
            return
        if event.type == "plan.updated":
            payload = {
                "stage": "tool_plan",
                "turn_id": event.turn_id,
                "items": event.payload.get("items") or [],
            }
            if self._event_store_available():
                publish_event(
                    self.db,
                    self.runtime_run.id,
                    RuntimeEventDraft(
                        type=RuntimeEventType.PLAN_PROPOSED,
                        parent_event_id=self._active_turn_event_id,
                        public_summary=event.summary or "已更新执行计划。",
                        payload=payload,
                    ),
                )
                async for rendered in self._flush_core_events():
                    yield rendered
            else:
                yield _sse(
                    "assistant.plan_updated",
                    {
                        "runtime_run_id": self.runtime_run.id,
                        "turn_id": event.turn_id,
                        "summary": event.summary or "已更新执行计划。",
                        "items": payload["items"],
                        "state": "thinking",
                    },
                )
            return
        if event.type == "tool.started":
            # The adapter prepared and committed RuntimeAction/capability.started
            # before this event was emitted.  Flush now, before the side effect.
            async for rendered in self._flush_core_events():
                yield rendered
            if not self._event_store_available():
                yield _sse(
                    "assistant.tool_started",
                    {
                        "runtime_run_id": self.runtime_run.id,
                        "turn_id": event.turn_id,
                        "tool_call_id": event.tool_call_id,
                        "tool_name": event.tool_name,
                        "state": "executing_tool",
                    },
                )
            return
        if event.type == "tool.succeeded":
            if event.tool_name:
                self._completed_capabilities.append(event.tool_name)
                if event.tool_name in {"create_project", "create_demo_workspace"}:
                    project_id = event.payload.get("result", {}).get("id") if isinstance(event.payload.get("result"), dict) else None
                    if isinstance(project_id, str):
                        self._set_active_project(project_id)
            self._consecutive_tool_failures = 0
            async for rendered in self._flush_core_events():
                yield rendered
            if not self._event_store_available():
                yield _sse(
                    "assistant.tool_succeeded",
                    {
                        "runtime_run_id": self.runtime_run.id,
                        "turn_id": event.turn_id,
                        "tool_call_id": event.tool_call_id,
                        "tool_name": event.tool_name,
                        "result": event.payload.get("result") or {},
                        "summary": event.summary,
                        "state": "completed",
                    },
                )
            return
        if event.type == "tool.failed":
            if event.tool_name:
                self._failed_capabilities.append(event.tool_name)
            self._consecutive_tool_failures += 1
            async for rendered in self._flush_core_events():
                yield rendered
            if not self._event_store_available():
                yield _sse(
                    "assistant.tool_failed",
                    {
                        "runtime_run_id": self.runtime_run.id,
                        "turn_id": event.turn_id,
                        "tool_call_id": event.tool_call_id,
                        "tool_name": event.tool_name,
                        "error_code": event.payload.get("error_code"),
                        "error_message": event.summary,
                        "state": "failed",
                    },
                )
            return
        if event.type == "tool.blocked":
            # Denied RuntimeActions already emit a failure.  Unavailable tools
            # do not create an action, so give them a durable public trace here.
            if event.payload.get("error_code") == "capability_unavailable":
                publish_event(
                    self.db,
                    self.runtime_run.id,
                    RuntimeEventDraft(
                        type=RuntimeEventType.CAPABILITY_FAILED,
                        parent_event_id=self._active_turn_event_id,
                        public_summary=event.summary or "请求了不可用的工具。",
                        payload={
                            "capability": event.tool_name,
                            "turn_id": event.turn_id,
                            "tool_call_id": event.tool_call_id,
                            "reason_code": "capability_unavailable",
                        },
                    ),
                )
            self._consecutive_tool_failures += 1
            async for rendered in self._flush_core_events():
                yield rendered
            return
        if event.type == "tool.paused":
            pause_reason = event.payload.get("pause_reason")
            if pause_reason == "needs_input":
                message = event.summary or "还需要补充必要信息。"
                save_message(self.db, self.conversation_id, "assistant", message)
                try:
                    complete_runtime_run(
                        self.db,
                        self.runtime_run.id,
                        message,
                        parent_event_id=self._active_turn_event_id,
                        terminal_state="needs_input",
                    )
                except ValueError:
                    pass
            elif pause_reason == "needs_approval":
                # Approval is a run boundary, not a model error.  The client
                # must receive an explicit terminal state so its composer can
                # leave the pending state and render the confirmation affordance.
                async for rendered in self._flush_core_events():
                    yield rendered
                async for rendered in self._emit_end_once(state="needs_confirmation"):
                    yield rendered
                return
            async for rendered in self._flush_core_events():
                yield rendered
            return
        if event.type == "turn.completed":
            summary = build_turn_summary(self._completed_capabilities[-self.max_tools_per_turn :])
            hook_context.step = int((event.turn_id or "turn-0").removeprefix("turn-") or 0)
            from .hooks import default_hook_registry

            default_hook_registry.trigger("TurnEnd", hook_context, tools=self._completed_capabilities, summary=summary)
            if self._publish_turn_finished(turn_id=event.turn_id or "turn-unknown", summary=summary):
                async for rendered in self._flush_core_events():
                    yield rendered
            return
        if event.type == "message.completed":
            text = (event.summary or "").strip() or "我可以继续帮你处理这个请求。"
            deltas_persisted = self._publish_visible_message_deltas(
                parent_event_id=self._active_turn_event_id,
                turn_id=event.turn_id or "turn-unknown",
                content=text,
            )
            save_message(self.db, self.conversation_id, "assistant", text)
            complete_runtime_run(
                self.db,
                self.runtime_run.id,
                text,
                parent_event_id=self._active_turn_event_id,
                message_delta_emitted=deltas_persisted,
            )
            async for rendered in self._flush_core_events(pace_message_deltas=deltas_persisted):
                yield rendered
            if not deltas_persisted:
                yield _sse(
                    "assistant.message",
                    {
                        "runtime_run_id": self.runtime_run.id,
                        "turn_id": event.turn_id,
                        "content": text,
                        "state": "completed",
                    },
                )
                async for rendered in self._emit_end_once(state="completed"):
                    yield rendered
            return
        if event.type == "run.paused":
            return
        if event.type == "run.cancelled":
            run = finalize_requested_runtime_cancellation(self.db, self.runtime_run.id)
            if run.status == "cancelled":
                message = str((run.result_json or {}).get("message") or "已取消这次操作。")
                save_message(self.db, self.conversation_id, "assistant", message)
            async for rendered in self._flush_core_events():
                yield rendered
            return
        if event.type == "run.failed":
            message = str(event.payload.get("public_message") or "助手暂时无法完成本次请求，请稍后重试。")
            try:
                fail_runtime_run(
                    self.db,
                    self.runtime_run.id,
                    message,
                    error_code=str(event.payload.get("error_code") or "harness_loop_failed"),
                    parent_event_id=self._active_turn_event_id,
                )
            except ValueError:
                pass
            save_message(self.db, self.conversation_id, "assistant", message)
            async for rendered in self._flush_core_events():
                yield rendered
            return
        if event.type == "run.step_limit":
            message = "为避免重复执行，我已达到本次任务的操作上限。请确认下一步后再继续。"
            save_message(self.db, self.conversation_id, "assistant", message)
            complete_runtime_run(
                self.db,
                self.runtime_run.id,
                message,
                parent_event_id=self._active_turn_event_id,
                terminal_state=HarnessTerminalState.STEP_LIMIT.value,
            )
            async for rendered in self._flush_core_events():
                yield rendered

    def _set_active_project(self, project_id: str) -> None:
        self.active_project_id = project_id

    async def _flush_core_events(self, **kwargs: Any) -> AsyncGenerator[str, None]:
        """Render durable events only when this Host has a durable store.

        The public path always has one.  The fallback keeps unit doubles and
        local provider-contract tests honest without treating their in-memory
        SSE as a persisted trace.
        """
        if not self._event_store_available():
            return
        async for rendered in self._flush_new_events(**kwargs):
            yield rendered

    @staticmethod
    def _core_failure_message(_exc: Exception) -> str:
        return "助手暂时无法完成本次请求，请稍后重试。"


def _to_core_messages(messages: Sequence[BaseMessage]) -> list[HarnessMessage]:
    result: list[HarnessMessage] = []
    for message in messages:
        if isinstance(message, SystemMessage):
            role = "system"
        elif isinstance(message, HumanMessage):
            role = "user"
        elif isinstance(message, ToolMessage):
            result.append(
                {
                    "role": "tool",
                    "tool_call_id": message.tool_call_id,
                    "name": getattr(message, "name", None),
                    "content": _extract_public_text_content(message.content),
                }
            )
            continue
        elif isinstance(message, AIMessage):
            tool_calls = []
            for call in message.tool_calls or []:
                if not isinstance(call, Mapping):
                    continue
                tool_calls.append(
                    {
                        "id": str(call.get("id") or new_tool_call_id()),
                        "type": "function",
                        "function": {
                            "name": str(call.get("name") or ""),
                            "arguments": json.dumps(call.get("args") or {}, ensure_ascii=False),
                        },
                    }
                )
            payload: HarnessMessage = {"role": "assistant", "content": _extract_public_text_content(message.content)}
            if tool_calls:
                payload["tool_calls"] = tool_calls
            result.append(payload)
            continue
        else:
            role = "user"
        result.append({"role": role, "content": _extract_public_text_content(message.content)})
    return result


def _to_langchain_messages(messages: Sequence[HarnessMessage]) -> list[BaseMessage]:
    result: list[BaseMessage] = []
    for message in messages:
        role = str(message.get("role") or "user")
        content = str(message.get("content") or "")
        if role == "system":
            result.append(SystemMessage(content=content))
        elif role == "assistant":
            calls: list[dict[str, Any]] = []
            for raw_call in message.get("tool_calls") or []:
                if not isinstance(raw_call, Mapping):
                    continue
                function = raw_call.get("function") if isinstance(raw_call.get("function"), Mapping) else {}
                raw_arguments = function.get("arguments") if isinstance(function, Mapping) else {}
                try:
                    arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else dict(raw_arguments or {})
                except (TypeError, json.JSONDecodeError):
                    arguments = {}
                calls.append(
                    {
                        "id": str(raw_call.get("id") or new_tool_call_id()),
                        "name": str(function.get("name") or ""),
                        "args": arguments if isinstance(arguments, dict) else {},
                    }
                )
            result.append(AIMessage(content=content, tool_calls=calls))
        elif role == "tool":
            result.append(ToolMessage(content=content, tool_call_id=str(message.get("tool_call_id") or new_tool_call_id())))
        else:
            result.append(HumanMessage(content=content))
    return result


def _to_core_tool_definition(spec: Mapping[str, Any]) -> HarnessToolDefinition:
    function = spec.get("function") if isinstance(spec.get("function"), Mapping) else {}
    return HarnessToolDefinition(
        name=str(function.get("name") or ""),
        description=str(function.get("description") or ""),
        parameters=dict(function.get("parameters") or {}),
        provider_spec=dict(spec),
    )


def _usage_payload(measurement: Any) -> dict[str, Any] | None:
    if measurement is None:
        return None
    return {
        key: value
        for key, value in {
            "input_tokens": getattr(measurement, "input_tokens", None),
            "output_tokens": getattr(measurement, "output_tokens", None),
            "total_tokens": getattr(measurement, "total_tokens", None),
        }.items()
        if value is not None
    }


__all__ = ["CoreStreamingHarness", "LangChainHarnessModelPort"]
