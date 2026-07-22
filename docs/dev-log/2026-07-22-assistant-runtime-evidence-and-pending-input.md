# Assistant Runtime Evidence and Pending Input

- Date: 2026-07-22
- Scope: Operator missing-input lifecycle, offline AssistantBench runtime capture, and release-gate evidence
- Status: implementation and local verification complete; reviewed production evidence pending

## What Changed

1. Added a shared bounded task-state helper for Assistant continuations. It
   persists only a capability name, redacted arguments, and missing field names
   for 30 minutes.
2. Extended the LangGraph Operator plan schema with `needs_input`. The graph
   records a redacted `plan.proposed` event and the SSE compatibility layer
   emits `assistant.intent_detected` followed by `assistant.missing_input`
   before the terminal assistant message.
3. Passed pending-input context into the next bounded Operator planner turn,
   then clears the state once the planner switches to an answer or a tool.
4. Added read-only `AssistantBench` runtime capture. A private manifest maps
   approved benchmark cases to Operator runs; output contains only structured
   routing/policy facts and omits messages, values, ids, checkpoints, raw tool
   outputs, and model payloads.
5. Made AssistantBench the fourth required report in the release quality gate,
   with explicit policy thresholds for route, missing-input, argument, policy,
   typed-confirmation, project-scope, and unknown-capability safety.

## Verification

- Operator graph missing-input lifecycle and endpoint continuation tests pass.
- Runtime capture tests prove tool and needs-input traces score from durable
  records without leaking a runtime id, a user message, or an argument value.
- Release-gate and rehearsal-script tests pass with the four-report contract.
- Operator integration tests now stub model and retrieval construction, so
  their results do not depend on provider/network availability.

## Remaining Evidence

- Run reviewed regression/hidden cases against an approved provider/model from
  the release commit.
- Keep the private capture manifest and the generated report in controlled
  release storage with two-person review and attestation.
- Do not treat the visible deterministic control fixture as release evidence.
