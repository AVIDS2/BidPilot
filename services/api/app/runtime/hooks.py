"""Harness lifecycle hooks (learn-claude-code style).

Design motto: hook around the loop, never rewrite the loop.

Supported events:
- UserPromptSubmit: after user message is accepted, before model call
- PreToolUse: before execute_capability; non-None return blocks the tool
- PostToolUse: after tool execution
- TurnEnd: after a model step finishes (text or tools)
- Stop: about to end the run; return force-continue reason to keep going
- TaskCompleted: background long task finished (wake signal)

This module is intentionally tiny and in-process. Product policy still lives in
execute_capability / approvals / quotas.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


HookCallback = Callable[..., Any]


@dataclass
class HookContext:
    conversation_id: str
    runtime_run_id: str
    user_id: str
    project_id: str | None = None
    step: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class HarnessHookRegistry:
    def __init__(self) -> None:
        self._hooks: dict[str, list[HookCallback]] = {
            "UserPromptSubmit": [],
            "PreToolUse": [],
            "PostToolUse": [],
            "TurnEnd": [],
            "Stop": [],
            "TaskCompleted": [],
        }

    def register(self, event: str, callback: HookCallback) -> None:
        if event not in self._hooks:
            raise ValueError(f"Unknown hook event: {event}")
        self._hooks[event].append(callback)

    def clear(self, event: str | None = None) -> None:
        if event is None:
            for key in self._hooks:
                self._hooks[key] = []
            return
        if event not in self._hooks:
            raise ValueError(f"Unknown hook event: {event}")
        self._hooks[event] = []

    def trigger(self, event: str, *args: Any, **kwargs: Any) -> list[Any]:
        if event not in self._hooks:
            raise ValueError(f"Unknown hook event: {event}")
        results: list[Any] = []
        for callback in self._hooks[event]:
            results.append(callback(*args, **kwargs))
        return results

    def first_blocking(self, event: str, *args: Any, **kwargs: Any) -> Any | None:
        """Return the first non-None result (used by PreToolUse / Stop)."""
        for value in self.trigger(event, *args, **kwargs):
            if value is not None:
                return value
        return None


# Process-wide default registry. Tests can swap callbacks via register/clear.
default_hook_registry = HarnessHookRegistry()


def register_default_recovery_hooks(registry: HarnessHookRegistry | None = None) -> None:
    """Install built-in multi-step recovery hooks once."""
    reg = registry or default_hook_registry

    def _stop_if_incomplete(ctx: HookContext, *, open_tools: int, max_steps: int, step: int) -> str | None:
        # Force one more turn when tools ran this step but model produced no final
        # answer and we still have budget. Guarded by step count.
        if open_tools <= 0:
            return None
        if step + 1 >= max_steps:
            return None
        if ctx.metadata.get("stop_hook_active"):
            return None
        return (
            "本轮调用了工具但尚未给出最终结论。请根据工具结果继续推进，"
            "必要时换策略；不要重复相同失败参数。"
        )

    # Avoid double-registering in reload scenarios.
    if not reg._hooks["Stop"]:
        reg.register("Stop", _stop_if_incomplete)


__all__ = [
    "HarnessHookRegistry",
    "HookContext",
    "default_hook_registry",
    "register_default_recovery_hooks",
]
