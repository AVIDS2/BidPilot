# Streaming Harness + Transcript Foundations

## Scope

Replaced the production assistant main path from batch structured-plan
`OperatorPlan` + `graph.invoke()` with a thin streaming tool-calling harness
inspired by Pi coding agent:

1. native model tool calls
2. multi-step loop with hard max steps
3. live SSE for text delta and tool lifecycle
4. every side effect still goes through `execute_capability`

Frontend matching now prefers `tool_call_id`, and assistant narrative text is no
longer buffered behind open tool activity. A pure transcript aggregator was
added for L1 turn grouping.

## Why

The previous operator path felt stuck, fragile, and repetitive because it:

- planned one capability at a time via structured output
- defaulted `continue_after_tool=false`
- invoked the whole graph before emitting events
- matched UI execution items mainly by tool name

## Key files

- `services/api/app/runtime/harness_loop.py` (new)
- `services/api/app/runtime/operator_adapter.py` (routes to harness by default)
- `apps/web/src/lib/ai-assistant-store.tsx`
- `apps/web/src/lib/assistant-transcript.ts`
- `apps/web/src/components/ai-assistant/assistant-activity-timeline.tsx`

## Rollout

Default on via `DOCPILOT_ASSISTANT_STREAMING_HARNESS=true`.

Set to `false` to fall back to the previous LangGraph operator planner path.

## Verification

- API: `tests/runtime/test_harness_loop.py` — 5 passed
- Web: assistant transcript + panel tests — 27 passed
- Ruff: harness files clean
