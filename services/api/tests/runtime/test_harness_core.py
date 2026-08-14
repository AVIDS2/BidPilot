"""Cross-domain contract tests for the framework-neutral harness loop."""

from __future__ import annotations

import json
import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from app.runtime.harness_core import (
    HarnessExecutionContext,
    HarnessLoop,
    HarnessLoopConfig,
    HarnessModelFailure,
    HarnessModelStep,
    HarnessPlanUpdate,
    HarnessTerminalState,
    HarnessToolCall,
    HarnessToolDefinition,
    HarnessToolOutcome,
)


@dataclass
class ScriptedModel:
    steps: deque[HarnessModelStep]
    seen_messages: list[list[dict[str, Any]]] = field(default_factory=list)

    async def next_step(self, messages, _tools) -> HarnessModelStep:
        self.seen_messages.append([dict(message) for message in messages])
        return self.steps.popleft()


@dataclass
class ScriptedExecutor:
    outcomes: dict[str, deque[HarnessToolOutcome]]
    calls: list[tuple[HarnessToolCall, HarnessExecutionContext]] = field(default_factory=list)

    async def execute(self, call: HarnessToolCall, context: HarnessExecutionContext) -> HarnessToolOutcome:
        self.calls.append((call, context))
        return self.outcomes[call.name].popleft()


TOOLS = (
    HarnessToolDefinition("read_note", "Read a saved note", {"type": "object"}),
    HarnessToolDefinition("write_note", "Write a saved note", {"type": "object"}),
    HarnessToolDefinition("failing_tool", "Fails deterministically", {"type": "object"}),
)


def step(text: str = "", *calls: HarnessToolCall) -> HarnessModelStep:
    return HarnessModelStep(text=text, tool_calls=tuple(calls))


def call(identifier: str, name: str, **arguments: Any) -> HarnessToolCall:
    return HarnessToolCall(id=identifier, name=name, arguments=arguments)


async def run_loop(
    model_steps: list[HarnessModelStep],
    outcomes: dict[str, list[HarnessToolOutcome]],
    **kwargs: Any,
):
    executor = ScriptedExecutor({name: deque(items) for name, items in outcomes.items()})
    loop = HarnessLoop(
        run_id="test-run",
        model=ScriptedModel(deque(model_steps)),
        executor=executor,
        tools=TOOLS,
        **kwargs,
    )
    result = await loop.run([{"role": "user", "content": "help me"}])
    return result, loop, executor


def _run(coroutine):
    return asyncio.run(coroutine)


def test_plain_conversation_completes_without_a_tool() -> None:
    result, _loop, executor = _run(run_loop([step("Hello. What can I help with?")], {}))

    assert result.terminal_state is HarnessTerminalState.COMPLETED
    assert result.final_text == "Hello. What can I help with?"
    assert executor.calls == []
    assert [event.type for event in result.events] == ["run.started", "turn.started", "message.completed", "run.completed"]


def test_generic_multi_tool_turn_preserves_model_order_and_result_context() -> None:
    result, loop, executor = _run(run_loop(
        [
            step("", call("read-1", "read_note", key="today"), call("write-1", "write_note", key="tomorrow")),
            step("I read the note and saved the follow-up."),
        ],
        {
            "read_note": [HarnessToolOutcome.succeeded("note read", {"text": "buy tea"})],
            "write_note": [HarnessToolOutcome.succeeded("note saved", {"saved": True})],
        },
    ))

    assert result.terminal_state is HarnessTerminalState.COMPLETED
    assert [item[0].name for item in executor.calls] == ["read_note", "write_note"]
    assert result.completed_tool_names == ("read_note", "write_note")
    second_turn = loop.model.seen_messages[1]  # type: ignore[attr-defined]
    tool_messages = [message for message in second_turn if message["role"] == "tool"]
    assert [message["name"] for message in tool_messages] == ["read_note", "write_note"]
    assert json.loads(tool_messages[0]["content"])["result"] == {"text": "buy tea"}
    assert json.loads(tool_messages[1]["content"])["result"] == {"saved": True}


def test_failed_tool_becomes_model_visible_and_the_model_can_correct_it() -> None:
    result, loop, executor = _run(run_loop(
        [
            step("", call("bad-1", "failing_tool", value="bad")),
            step("", call("read-2", "read_note", key="fixed")),
            step("Recovered after using the correct tool."),
        ],
        {
            "failing_tool": [HarnessToolOutcome.failed("value must be a valid note key", error_code="invalid_argument")],
            "read_note": [HarnessToolOutcome.succeeded("note read", {"text": "ok"})],
        },
    ))

    assert result.terminal_state is HarnessTerminalState.COMPLETED
    assert result.failed_tool_names == ("failing_tool",)
    assert result.completed_tool_names == ("read_note",)
    assert [entry[0].name for entry in executor.calls] == ["failing_tool", "read_note"]
    recovery_turn = loop.model.seen_messages[1]  # type: ignore[attr-defined]
    failure = next(message for message in recovery_turn if message["role"] == "tool")
    assert json.loads(failure["content"])["error_code"] == "invalid_argument"


def test_unknown_tool_is_blocked_without_calling_the_executor() -> None:
    result, _loop, executor = _run(run_loop(
        [step("", call("unknown-1", "unknown_tool")), step("That tool is unavailable.")],
        {},
    ))

    assert result.terminal_state is HarnessTerminalState.FAILED
    assert executor.calls == []
    blocked = next(event for event in result.events if event.type == "tool.blocked")
    assert blocked.payload["error_code"] == "tool_unavailable"


def test_paused_tool_is_a_normal_terminal_pause() -> None:
    result, _loop, executor = _run(run_loop(
        [step("", call("write-1", "write_note", key="tomorrow"))],
        {"write_note": [HarnessToolOutcome.paused("approval needed", pause_reason="needs_approval")]},
    ))

    assert result.terminal_state is HarnessTerminalState.PAUSED
    assert result.pause_reason == "needs_approval"
    assert [entry[0].name for entry in executor.calls] == ["write_note"]
    assert result.events[-1].type == "run.paused"


def test_preflight_can_pause_without_exposing_a_tool_as_started() -> None:
    class ApprovalExecutor:
        execute_called = False

        async def prepare(self, _call, _context):
            return HarnessToolOutcome.paused("approval needed", pause_reason="needs_approval")

        async def execute(self, _call, _context):
            self.execute_called = True
            return HarnessToolOutcome.succeeded("unexpected")

    executor = ApprovalExecutor()
    loop = HarnessLoop(
        run_id="run",
        model=ScriptedModel(deque([step("", call("write-1", "write_note", key="tomorrow"))])),
        executor=executor,
        tools=TOOLS,
    )

    result = _run(loop.run([{"role": "user", "content": "write a note"}]))

    assert result.terminal_state is HarnessTerminalState.PAUSED
    assert executor.execute_called is False
    assert "tool.started" not in [event.type for event in result.events]
    assert [event.type for event in result.events][-2:] == ["tool.paused", "run.paused"]


def test_preflight_runs_before_the_started_event_and_side_effect() -> None:
    observed: list[str] = []

    class PreparedExecutor:
        async def prepare(self, _call, _context):
            observed.append("prepared")
            return None

        async def execute(self, _call, _context):
            observed.append("executed")
            return HarnessToolOutcome.succeeded("note read")

    loop = HarnessLoop(
        run_id="run",
        model=ScriptedModel(deque([step("", call("read-1", "read_note", key="today")), step("done")])),
        executor=PreparedExecutor(),
        tools=TOOLS,
    )

    result = _run(loop.run([{"role": "user", "content": "read"}]))

    started_index = next(index for index, event in enumerate(result.events) if event.type == "tool.started")
    assert observed == ["prepared", "executed"]
    assert result.events[started_index].tool_name == "read_note"


def test_cancellation_stops_before_the_next_model_turn() -> None:
    # The loop probes before a turn and before a tool.  Let the first read
    # finish, then cancel before it could request the next model turn.
    checks = iter([False, False, True])
    result, _loop, executor = _run(run_loop(
        [step("", call("read-1", "read_note", key="one")), step("not reached")],
        {"read_note": [HarnessToolOutcome.succeeded("note read")]},
        cancellation_check=lambda: next(checks),
    ))

    assert result.terminal_state is HarnessTerminalState.CANCELLED
    assert len(executor.calls) == 1
    assert result.turns == 1


def test_steering_input_preempts_following_calls_at_a_tool_boundary() -> None:
    steering = deque(["Stop writing; only read it.", None])
    result, loop, executor = _run(run_loop(
        [
            step("", call("read-1", "read_note", key="one"), call("write-1", "write_note", key="two")),
            step("I will only read it."),
        ],
        {
            "read_note": [HarnessToolOutcome.succeeded("note read")],
            "write_note": [HarnessToolOutcome.succeeded("note saved")],
        },
        steering_input_provider=lambda: steering.popleft(),
    ))

    assert result.terminal_state is HarnessTerminalState.COMPLETED
    assert [entry[0].name for entry in executor.calls] == ["read_note"]
    assert any(event.type == "steering.accepted" for event in result.events)
    assert any(message.get("content") == "Stop writing; only read it." for message in loop.model.seen_messages[1])  # type: ignore[attr-defined]


def test_plan_policy_is_observable_but_never_executes_tools_itself() -> None:
    class PlanPolicy:
        def update(self, *, messages, calls, context):
            del messages, context
            return HarnessPlanUpdate("generic plan", tuple(call.name for call in calls))

    result, _loop, executor = _run(run_loop(
        [step("", call("read-1", "read_note", key="today")), step("done")],
        {"read_note": [HarnessToolOutcome.succeeded("note read")]},
        plan_policy=PlanPolicy(),
    ))

    plan_event = next(event for event in result.events if event.type == "plan.updated")
    assert plan_event.payload == {"items": ["read_note"]}
    assert [entry[0].name for entry in executor.calls] == ["read_note"]


def test_followup_input_runs_on_a_turn_boundary_without_replaying_tools() -> None:
    followups = deque(["Now summarize it.", None])
    result, loop, executor = _run(run_loop(
        [step("I found the note."), step("Summary: buy tea.")],
        {},
        followup_input_provider=lambda: followups.popleft(),
    ))

    assert result.terminal_state is HarnessTerminalState.COMPLETED
    assert result.turns == 2
    assert result.final_text == "Summary: buy tea."
    assert result.resume_cursor == len(result.events)
    assert executor.calls == []
    assert any(event.type == "followup.accepted" for event in result.events)
    assert any(message.get("content") == "Now summarize it." for message in loop.model.seen_messages[1])  # type: ignore[attr-defined]


def test_failure_budget_terminates_repeated_failures() -> None:
    result, _loop, executor = _run(run_loop(
        [
            step("", call("fail-1", "failing_tool")),
            step("", call("fail-2", "failing_tool")),
            step("", call("fail-3", "failing_tool")),
        ],
        {"failing_tool": [HarnessToolOutcome.failed("failed")] * 3},
        config=HarnessLoopConfig(max_consecutive_failures=3),
    ))

    assert result.terminal_state is HarnessTerminalState.FAILED
    assert len(executor.calls) == 3
    assert result.events[-1].summary == "tool failure budget exhausted"


def test_nonrecoverable_failure_preserves_its_public_message_for_the_host() -> None:
    result, _loop, _executor = _run(run_loop(
        [step("", call("import-1", "failing_tool"))],
        {
            "failing_tool": [
                HarnessToolOutcome.failed(
                    "origin rejected the artifact; automatic retries stopped",
                    error_code="remote_http_status",
                    recoverable=False,
                )
            ]
        },
    ))

    assert result.terminal_state is HarnessTerminalState.FAILED
    assert result.events[-1].payload["public_message"] == "origin rejected the artifact; automatic retries stopped"
    assert result.events[-1].payload["error_code"] == "remote_http_status"


def test_step_limit_is_explicit_when_model_never_finishes() -> None:
    result, _loop, executor = _run(run_loop(
        [step("", call("read-1", "read_note")), step("", call("read-2", "read_note"))],
        {"read_note": [HarnessToolOutcome.succeeded("read"), HarnessToolOutcome.succeeded("read")]},
        config=HarnessLoopConfig(max_steps=2),
    ))

    assert result.terminal_state is HarnessTerminalState.STEP_LIMIT
    assert len(executor.calls) == 2
    assert result.events[-1].type == "run.step_limit"


def test_executor_exception_is_redacted_and_model_can_continue() -> None:
    class RaisingExecutor:
        calls = 0

        async def execute(self, call, _context):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("token=should-not-escape")
            return HarnessToolOutcome.succeeded("note read")

    model = ScriptedModel(
        deque(
            [
                step("", call("first", "read_note")),
                step("", call("second", "read_note")),
                step("Recovered."),
            ]
        )
    )
    loop = HarnessLoop(run_id="run", model=model, executor=RaisingExecutor(), tools=TOOLS)
    result = _run(loop.run([{"role": "user", "content": "test"}]))

    assert result.terminal_state is HarnessTerminalState.COMPLETED
    failed_message = next(message for message in model.seen_messages[1] if message["role"] == "tool")
    assert "should-not-escape" not in failed_message["content"]
    assert json.loads(failed_message["content"])["error_code"] == "tool_execution_failed"


def test_model_port_can_return_an_explicit_safe_failure_message() -> None:
    class LimitedModel:
        async def next_step(self, _messages, _tools):
            raise HarnessModelFailure("workspace budget exhausted", error_code="usage_limit_exceeded")

    loop = HarnessLoop(run_id="run", model=LimitedModel(), executor=ScriptedExecutor({}), tools=TOOLS)
    result = _run(loop.run([{"role": "user", "content": "help"}]))

    assert result.terminal_state is HarnessTerminalState.FAILED
    assert result.events[-1].payload["public_message"] == "workspace budget exhausted"
    assert result.events[-1].payload["error_code"] == "usage_limit_exceeded"
