"""Framework-neutral, Pi-style tool-use loop.

This module deliberately has no knowledge of BidPilot capabilities, database
models, HTTP/SSE, or LangGraph.  A host owns persistence and presentation;
the loop owns only the model -> tools -> model control flow and its stable
in-memory trace.  That separation makes the harness testable with ordinary
tools before a product adapter is attached.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from inspect import isawaitable
from typing import Any, Protocol
from uuid import uuid4


JsonObject = dict[str, Any]
HarnessMessage = dict[str, Any]


class ToolOutcomeKind(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PAUSED = "paused"
    BLOCKED = "blocked"


class HarnessTerminalState(StrEnum):
    COMPLETED = "completed"
    PAUSED = "paused"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STEP_LIMIT = "step_limit"


class HarnessModelFailure(RuntimeError):
    """A model-port failure with an explicitly safe message for the user."""

    def __init__(self, public_message: str, *, error_code: str = "model_unavailable") -> None:
        super().__init__(public_message)
        self.public_message = public_message
        self.error_code = error_code


@dataclass(frozen=True)
class HarnessToolDefinition:
    """A provider-neutral tool descriptor.

    ``provider_spec`` remains opaque to the loop so a host can expose the
    schema required by LangChain, OpenAI-compatible APIs, or another adapter.
    ``parallel_safe`` is intentionally metadata only for now; sequential
    execution keeps dependent actions and durable audit trails explainable.
    """

    name: str
    description: str
    parameters: JsonObject
    parallel_safe: bool = False
    provider_spec: JsonObject | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.replace("_", "").replace("-", "").isalnum():
            raise ValueError("tool name must be a non-empty identifier")
        if not isinstance(self.parameters, dict):
            raise TypeError("tool parameters must be a JSON object")


@dataclass(frozen=True)
class HarnessToolCall:
    id: str
    name: str
    arguments: JsonObject

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("tool call id must not be empty")
        if not self.name:
            raise ValueError("tool call name must not be empty")
        if not isinstance(self.arguments, dict):
            raise TypeError("tool call arguments must be a JSON object")


@dataclass(frozen=True)
class HarnessModelStep:
    text: str = ""
    tool_calls: tuple[HarnessToolCall, ...] = ()
    usage: JsonObject | None = None


@dataclass(frozen=True)
class HarnessToolOutcome:
    kind: ToolOutcomeKind
    public_summary: str
    model_payload: JsonObject = field(default_factory=dict)
    error_code: str | None = None
    pause_reason: str | None = None
    recoverable: bool = True

    @classmethod
    def succeeded(cls, public_summary: str, model_payload: Mapping[str, Any] | None = None) -> "HarnessToolOutcome":
        return cls(
            kind=ToolOutcomeKind.SUCCEEDED,
            public_summary=public_summary,
            model_payload=dict(model_payload or {}),
        )

    @classmethod
    def failed(
        cls,
        public_summary: str,
        *,
        error_code: str = "tool_execution_failed",
        recoverable: bool = True,
        model_payload: Mapping[str, Any] | None = None,
    ) -> "HarnessToolOutcome":
        return cls(
            kind=ToolOutcomeKind.FAILED,
            public_summary=public_summary,
            error_code=error_code,
            recoverable=recoverable,
            model_payload=dict(model_payload or {}),
        )

    @classmethod
    def paused(
        cls,
        public_summary: str,
        *,
        pause_reason: str,
        model_payload: Mapping[str, Any] | None = None,
    ) -> "HarnessToolOutcome":
        return cls(
            kind=ToolOutcomeKind.PAUSED,
            public_summary=public_summary,
            pause_reason=pause_reason,
            model_payload=dict(model_payload or {}),
        )

    @classmethod
    def blocked(
        cls,
        public_summary: str,
        *,
        error_code: str = "tool_blocked",
    ) -> "HarnessToolOutcome":
        return cls(
            kind=ToolOutcomeKind.BLOCKED,
            public_summary=public_summary,
            error_code=error_code,
            recoverable=False,
        )


@dataclass(frozen=True)
class HarnessEvent:
    """Stable internal trace event, suitable for host persistence/projection."""

    type: str
    turn_id: str | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    summary: str | None = None
    payload: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class HarnessPlanUpdate:
    """A display-only execution plan proposed by a host-owned policy.

    The loop never executes a plan item. This keeps plan-and-execute useful
    for observability without making an LLM-generated plan product truth.
    """

    summary: str
    items: tuple[str, ...] = ()


@dataclass(frozen=True)
class HarnessRunResult:
    terminal_state: HarnessTerminalState
    final_text: str | None
    messages: tuple[HarnessMessage, ...]
    events: tuple[HarnessEvent, ...]
    completed_tool_names: tuple[str, ...]
    failed_tool_names: tuple[str, ...]
    turns: int
    pause_reason: str | None = None
    resume_cursor: int = 0


@dataclass(frozen=True)
class HarnessLoopConfig:
    max_steps: int = 24
    max_tools_per_turn: int = 4
    max_consecutive_failures: int = 3

    def __post_init__(self) -> None:
        if self.max_steps < 1:
            raise ValueError("max_steps must be positive")
        if self.max_tools_per_turn < 1:
            raise ValueError("max_tools_per_turn must be positive")
        if self.max_consecutive_failures < 1:
            raise ValueError("max_consecutive_failures must be positive")


@dataclass(frozen=True)
class HarnessExecutionContext:
    run_id: str
    turn_id: str
    step: int
    completed_tool_names: tuple[str, ...]
    failed_tool_names: tuple[str, ...]


class HarnessModelPort(Protocol):
    async def next_step(
        self,
        messages: Sequence[HarnessMessage],
        tools: Sequence[HarnessToolDefinition],
    ) -> HarnessModelStep: ...


class HarnessToolExecutor(Protocol):
    async def execute(
        self,
        call: HarnessToolCall,
        context: HarnessExecutionContext,
    ) -> HarnessToolOutcome: ...


class HarnessToolPreparer(Protocol):
    """Optional preflight phase for a governed tool executor.

    A product adapter may persist an action, perform parameter/policy checks,
    or stop for human input before the loop exposes ``tool.started``.  It
    returns ``None`` only when the subsequent ``execute`` call is safe to run.
    Plain executors do not need to implement this protocol.
    """

    async def prepare(
        self,
        call: HarnessToolCall,
        context: HarnessExecutionContext,
    ) -> HarnessToolOutcome | None: ...


CancellationCheck = Callable[[], bool | Awaitable[bool]]
SteeringInputProvider = Callable[[], str | None | Awaitable[str | None]]
FollowupInputProvider = Callable[[], str | None | Awaitable[str | None]]


class HarnessPlanPolicy(Protocol):
    """Optional observer that can publish a non-authoritative plan."""

    def update(
        self,
        *,
        messages: Sequence[HarnessMessage],
        calls: Sequence[HarnessToolCall],
        context: HarnessExecutionContext,
    ) -> HarnessPlanUpdate | Awaitable[HarnessPlanUpdate | None] | None: ...


class HarnessLoop:
    """Generic sequential tool loop modelled after Pi's agent loop.

    The loop accepts standard OpenAI-style transcript dictionaries because this
    is easy to evaluate with AgentEvals and easy for model adapters to map.
    No generated event is persisted here: a host observes ``stream`` and
    writes events atomically with its own application state.
    """

    def __init__(
        self,
        *,
        run_id: str,
        model: HarnessModelPort,
        executor: HarnessToolExecutor,
        tools: Sequence[HarnessToolDefinition],
        config: HarnessLoopConfig | None = None,
        cancellation_check: CancellationCheck | None = None,
        steering_input_provider: SteeringInputProvider | None = None,
        followup_input_provider: FollowupInputProvider | None = None,
        plan_policy: HarnessPlanPolicy | None = None,
    ) -> None:
        self.run_id = run_id
        self.model = model
        self.executor = executor
        self.tools = tuple(tools)
        self.config = config or HarnessLoopConfig()
        self.cancellation_check = cancellation_check
        self.steering_input_provider = steering_input_provider
        self.followup_input_provider = followup_input_provider
        self.plan_policy = plan_policy
        self._tool_names = frozenset(tool.name for tool in self.tools)
        self._events: list[HarnessEvent] = []
        self._messages: list[HarnessMessage] = []
        self._completed: list[str] = []
        self._failed: list[str] = []
        self._consecutive_failures = 0
        self._result: HarnessRunResult | None = None

    @property
    def result(self) -> HarnessRunResult | None:
        return self._result

    async def run(self, messages: Sequence[HarnessMessage]) -> HarnessRunResult:
        async for _event in self.stream(messages):
            pass
        assert self._result is not None
        return self._result

    async def stream(self, messages: Sequence[HarnessMessage]) -> AsyncIterator[HarnessEvent]:
        if self._result is not None:
            raise RuntimeError("a HarnessLoop instance can run only once")
        self._messages = [dict(message) for message in messages]
        if not self._messages:
            raise ValueError("at least one initial message is required")

        async for event in self._emit(HarnessEvent(type="run.started", summary="run started")):
            yield event

        for step in range(1, self.config.max_steps + 1):
            if await self._cancelled():
                async for event in self._finish(HarnessTerminalState.CANCELLED, summary="run cancelled", turns=step - 1):
                    yield event
                return

            turn_id = f"turn-{step}"
            async for event in self._emit(
                HarnessEvent(type="turn.started", turn_id=turn_id, payload={"step": step})
            ):
                yield event
            try:
                model_step = await self.model.next_step(tuple(self._messages), self.tools)
            except asyncio.CancelledError:
                raise
            except HarnessModelFailure as exc:
                async for event in self._finish(
                    HarnessTerminalState.FAILED,
                    summary="model unavailable",
                    turns=step,
                    public_message=exc.public_message,
                    error_code=exc.error_code,
                ):
                    yield event
                return
            except Exception:
                async for event in self._finish(
                    HarnessTerminalState.FAILED,
                    summary="model unavailable",
                    turns=step,
                ):
                    yield event
                return

            if not isinstance(model_step, HarnessModelStep):
                raise TypeError("model port must return HarnessModelStep")
            calls = model_step.tool_calls[: self.config.max_tools_per_turn]
            if not calls:
                final_text = model_step.text.strip()
                followup = await self._consume_followup_input()
                if followup:
                    self._messages.append({"role": "user", "content": followup})
                    async for event in self._emit(
                        HarnessEvent(type="followup.accepted", turn_id=turn_id, summary=followup)
                    ):
                        yield event
                    async for event in self._emit(HarnessEvent(type="turn.completed", turn_id=turn_id)):
                        yield event
                    continue
                async for event in self._emit(
                    HarnessEvent(type="message.completed", turn_id=turn_id, summary=final_text)
                ):
                    yield event
                async for event in self._finish(
                    HarnessTerminalState.COMPLETED,
                    summary="run completed",
                    final_text=final_text,
                    turns=step,
                ):
                    yield event
                return

            self._messages.append(_assistant_tool_message(model_step.text, calls))
            plan_update = await self._update_plan(calls, self._execution_context(turn_id=turn_id, step=step))
            async for event in self._emit(
                HarnessEvent(
                    type="turn.model_response",
                    turn_id=turn_id,
                    payload={"tool_call_count": len(calls), "usage": model_step.usage or {}},
                )
            ):
                yield event
            if plan_update is not None:
                async for event in self._emit(
                    HarnessEvent(
                        type="plan.updated",
                        turn_id=turn_id,
                        summary=plan_update.summary,
                        payload={"items": list(plan_update.items)},
                    )
                ):
                    yield event

            for call in calls:
                if await self._cancelled():
                    async for event in self._finish(HarnessTerminalState.CANCELLED, summary="run cancelled", turns=step):
                        yield event
                    return
                context = self._execution_context(turn_id=turn_id, step=step)
                prepared_outcome = await self._prepare_call(call, context)
                if prepared_outcome is not None:
                    outcome = prepared_outcome
                else:
                    async for event in self._emit(
                        HarnessEvent(
                            type="tool.started",
                            turn_id=turn_id,
                            tool_call_id=call.id,
                            tool_name=call.name,
                            payload={"arguments": dict(call.arguments)},
                        )
                    ):
                        yield event
                    outcome = await self._execute_call(call, context)
                self._messages.append(_tool_result_message(call, outcome))
                event_type = {
                    ToolOutcomeKind.SUCCEEDED: "tool.succeeded",
                    ToolOutcomeKind.FAILED: "tool.failed",
                    ToolOutcomeKind.PAUSED: "tool.paused",
                    ToolOutcomeKind.BLOCKED: "tool.blocked",
                }[outcome.kind]
                async for event in self._emit(
                    HarnessEvent(
                        type=event_type,
                        turn_id=turn_id,
                        tool_call_id=call.id,
                        tool_name=call.name,
                        summary=outcome.public_summary,
                        payload={
                            "error_code": outcome.error_code,
                            "pause_reason": outcome.pause_reason,
                            "recoverable": outcome.recoverable,
                            "result": outcome.model_payload,
                        },
                    )
                ):
                    yield event

                if outcome.kind is ToolOutcomeKind.PAUSED:
                    async for event in self._finish(
                        HarnessTerminalState.PAUSED,
                        summary=outcome.public_summary,
                        turns=step,
                        pause_reason=outcome.pause_reason,
                    ):
                        yield event
                    return
                if outcome.kind is ToolOutcomeKind.SUCCEEDED:
                    self._completed.append(call.name)
                    self._consecutive_failures = 0
                else:
                    self._failed.append(call.name)
                    self._consecutive_failures += 1
                    if not outcome.recoverable or self._consecutive_failures >= self.config.max_consecutive_failures:
                        async for event in self._finish(
                            HarnessTerminalState.FAILED,
                            summary="tool failure budget exhausted",
                            turns=step,
                            public_message=outcome.public_summary,
                            error_code=outcome.error_code,
                        ):
                            yield event
                        return

                steering = await self._consume_steering_input()
                if steering:
                    self._messages.append({"role": "user", "content": steering})
                    async for event in self._emit(
                        HarnessEvent(type="steering.accepted", turn_id=turn_id, summary=steering)
                    ):
                        yield event
                    break

            async for event in self._emit(HarnessEvent(type="turn.completed", turn_id=turn_id)):
                yield event

        async for event in self._finish(
            HarnessTerminalState.STEP_LIMIT,
            summary="step limit reached",
            turns=self.config.max_steps,
        ):
            yield event

    async def _execute_call(
        self,
        call: HarnessToolCall,
        context: HarnessExecutionContext,
    ) -> HarnessToolOutcome:
        try:
            outcome = await self.executor.execute(call, context)
        except asyncio.CancelledError:
            raise
        except Exception:
            return HarnessToolOutcome.failed("tool execution failed", recoverable=True)
        if not isinstance(outcome, HarnessToolOutcome):
            return HarnessToolOutcome.failed("tool returned an invalid outcome", error_code="tool_protocol_invalid")
        return outcome

    def _execution_context(self, *, turn_id: str, step: int) -> HarnessExecutionContext:
        return HarnessExecutionContext(
            run_id=self.run_id,
            turn_id=turn_id,
            step=step,
            completed_tool_names=tuple(self._completed),
            failed_tool_names=tuple(self._failed),
        )

    async def _prepare_call(
        self,
        call: HarnessToolCall,
        context: HarnessExecutionContext,
    ) -> HarnessToolOutcome | None:
        if call.name not in self._tool_names:
            return HarnessToolOutcome.blocked("requested tool is unavailable", error_code="tool_unavailable")
        prepare = getattr(self.executor, "prepare", None)
        if not callable(prepare):
            return None
        try:
            outcome = prepare(call, context)
            outcome = await outcome if isawaitable(outcome) else outcome
        except asyncio.CancelledError:
            raise
        except Exception:
            return HarnessToolOutcome.failed("tool preparation failed", recoverable=True)
        if outcome is not None and not isinstance(outcome, HarnessToolOutcome):
            return HarnessToolOutcome.failed("tool preparation returned an invalid outcome", error_code="tool_protocol_invalid")
        return outcome

    async def _cancelled(self) -> bool:
        if self.cancellation_check is None:
            return False
        checked = self.cancellation_check()
        return bool(await checked) if isawaitable(checked) else bool(checked)

    async def _consume_steering_input(self) -> str | None:
        if self.steering_input_provider is None:
            return None
        value = self.steering_input_provider()
        value = await value if isawaitable(value) else value
        return value.strip() if isinstance(value, str) and value.strip() else None

    async def _consume_followup_input(self) -> str | None:
        if self.followup_input_provider is None:
            return None
        value = self.followup_input_provider()
        value = await value if isawaitable(value) else value
        return value.strip() if isinstance(value, str) and value.strip() else None

    async def _update_plan(
        self,
        calls: Sequence[HarnessToolCall],
        context: HarnessExecutionContext,
    ) -> HarnessPlanUpdate | None:
        if self.plan_policy is None:
            return None
        try:
            update = self.plan_policy.update(messages=tuple(self._messages), calls=calls, context=context)
            update = await update if isawaitable(update) else update
        except asyncio.CancelledError:
            raise
        except Exception:
            # A display policy must never suppress the actual task.
            return None
        return update if isinstance(update, HarnessPlanUpdate) else None

    async def _emit(self, event: HarnessEvent) -> AsyncIterator[HarnessEvent]:
        self._events.append(event)
        yield event

    async def _finish(
        self,
        terminal_state: HarnessTerminalState,
        *,
        summary: str,
        turns: int,
        final_text: str | None = None,
        pause_reason: str | None = None,
        public_message: str | None = None,
        error_code: str | None = None,
    ) -> AsyncIterator[HarnessEvent]:
        event = HarnessEvent(
            type=f"run.{terminal_state.value}",
            summary=summary,
            payload={
                "terminal_state": terminal_state.value,
                "pause_reason": pause_reason,
                "public_message": public_message,
                "error_code": error_code,
            },
        )
        async for emitted in self._emit(event):
            yield emitted
        self._result = HarnessRunResult(
            terminal_state=terminal_state,
            final_text=final_text,
            messages=tuple(self._messages),
            events=tuple(self._events),
            completed_tool_names=tuple(self._completed),
            failed_tool_names=tuple(self._failed),
            turns=turns,
            pause_reason=pause_reason,
            resume_cursor=len(self._events),
        )


def _assistant_tool_message(text: str, calls: Sequence[HarnessToolCall]) -> HarnessMessage:
    return {
        "role": "assistant",
        "content": text,
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": json.dumps(call.arguments, ensure_ascii=False)},
            }
            for call in calls
        ],
    }


def _tool_result_message(call: HarnessToolCall, outcome: HarnessToolOutcome) -> HarnessMessage:
    payload = {
        "status": outcome.kind.value,
        "summary": outcome.public_summary,
        "error_code": outcome.error_code,
        "pause_reason": outcome.pause_reason,
        "recoverable": outcome.recoverable,
        "result": outcome.model_payload,
    }
    return {
        "role": "tool",
        "tool_call_id": call.id,
        "name": call.name,
        "content": json.dumps(payload, ensure_ascii=False, sort_keys=True),
    }


def new_tool_call_id() -> str:
    """Generate IDs for provider adapters that omit a tool-call identifier."""
    return f"call_{uuid4().hex[:16]}"


__all__ = [
    "HarnessEvent",
    "HarnessExecutionContext",
    "HarnessLoop",
    "HarnessLoopConfig",
    "HarnessMessage",
    "HarnessModelFailure",
    "HarnessModelPort",
    "HarnessModelStep",
    "HarnessPlanPolicy",
    "HarnessPlanUpdate",
    "HarnessRunResult",
    "HarnessTerminalState",
    "HarnessToolCall",
    "HarnessToolDefinition",
    "HarnessToolExecutor",
    "HarnessToolPreparer",
    "HarnessToolOutcome",
    "ToolOutcomeKind",
    "new_tool_call_id",
]
