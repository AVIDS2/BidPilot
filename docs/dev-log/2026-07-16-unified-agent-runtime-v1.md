# Unified Agent Runtime v1: Delivery Log

- Date: 2026-07-16
- Scope: durable runtime control plane, bounded operator graph, workflow event bridge, and client event replay
- Status: governed Operator is now the production default; release evidence and independent UI verification remain pending

## Why This Phase Exists

BidPilot previously had several partially overlapping execution descriptions: chat conversation state, Assistant audit rows, LangGraph checkpoints, Celery execution runs, and UI-only stream state. That is acceptable for a prototype but unsafe for an enterprise Agent because a reconnect, retry, approval, or worker restart can disagree about what happened.

The runtime v1 work introduces one product-owned description of user-visible work. It does not replace domain data or LangGraph persistence. It connects them safely.

## Delivered Runtime Model

1. `RuntimeRun` represents a visible unit of work: an Assistant turn, a linked workflow, or a recovery action.
2. `RuntimeEvent` is append-only, redacted before persistence, and sequenced per run. The UI can replay it using `after_sequence`.
3. `RuntimeAction` is the idempotency boundary for a capability invocation.
4. `RuntimeApproval` is a one-time, scoped approval record attached to one action.
5. Capability metadata, risk level, authorization, approval policy, public labels, and result formatting now live behind the runtime registry/policy boundary.

## Execution Engines

The deterministic local Assistant adapter and the production-default explicit LangGraph operator adapter use the same runtime service for every effect. The LangGraph graph is bounded to a small capability loop and pauses using `interrupt()` only after a durable approval exists. It resumes using `Command(resume=...)` on the stable conversation thread; each visible turn still has its own `RuntimeRun` for audit and idempotency.

Production uses `PostgresSaver` by default. Alembic migration and checkpoint-table setup are ordered deployment steps, not runtime side effects. There is no silent fallback to an in-memory checkpointer. In-memory checkpointing is accepted only when explicitly configured for tests or local development.

## Workflow Bridge

The long-running drafting graph remains a domain workflow with its own `ExecutionRun`. Starting it creates a linked `RuntimeRun(kind=workflow_bridge)`. Worker node start, success, failure, approval, and terminal states publish public runtime events. The API streaming route consumes those events; it does not read LangGraph checkpoint tables as a UI event source.

## Cancellation Contract

`POST /runtime/runs/{run_id}/cancel` accepts only an authorized linked workflow bridge. A queued or human-paused job becomes terminal immediately. A running job is marked `cancel_requested`; the Worker observes that durable state before and after every graph node, allows the active node to reach its own transaction boundary, then marks both `ExecutionRun` and `RuntimeRun` as `cancelled`.

The public timeline distinguishes cancellation from failure. The drafting SSE compatibility stream emits `graph_cancellation_requested` followed by `graph_cancelled`, and the mounted Assistant activity timeline shows a cancel control only when it has the safe bridge id. It never treats a cancellation as a failed workflow.

## Retry Lineage Contract

`POST /execution/runs/{run_id}/retry` and the `retry_run` capability now retry only terminal, runtime-linked `draft_section` and `redraft_section` work. They create a new child `ExecutionRun` with `parent_execution_run_id` and an incremented `attempt_number`; the old execution record is never reset or mutated. The child receives a new linked `RuntimeRun`, whose parent is the source workflow bridge.

Every retry rechecks project capability and the workflow quota, records a fresh usage event and an audit event, and dispatches a new Worker task. The source execution and its runtime bridge must both be in the same retryable terminal state before a retry is allowed, preventing a stale domain row from creating a duplicate concurrent workflow. The source must also be the leaf of its attempt chain; an in-flight child is returned idempotently and a completed child must be retried directly. A prior BYOK provider configuration is reused only when the requesting user still owns it. The workflow bridge stores a non-sensitive `provider_source` marker so deletion of a BYOK configuration is denied rather than silently falling back to a platform key. A legacy execution without a runtime bridge is rejected instead of guessing which provider or policy snapshot to replay.

## Approval Safety Boundary

The operator graph must be resumed through its LangGraph checkpoint. The generic REST approval endpoint therefore rejects a `langgraph_operator` approval with `409` rather than resolving the action directly and leaving the graph paused. Assistant confirmations use the graph resume path. A standalone approval workbench can later call a dedicated runtime-resume endpoint after it has the same provider/context resolution guarantees.

## Client Recovery

Compatibility SSE now carries `runtime_run_id` and `runtime_sequence` for durable events. The web Assistant advances a per-run cursor only for strictly newer events. If an Assistant stream closes before a terminal event, it requests `/runtime/runs/{id}/events?after_sequence=N`, translates only the public event contract back into UI timeline entries, and never repeats the original POST request.

## Verification Evidence

```powershell
$env:DOCPILOT_DATABASE_URL='postgresql+psycopg://docpilot:docpilot@localhost:5433/docpilot_migration_test'
uv run --directory services/api pytest -q
# 390 passed

uv run --directory services/worker pytest -q
# 51 passed

pnpm --filter @docpilot/web test -- --run
# 83 passed

pnpm --filter @docpilot/web build
# passed; existing chunk-size warning remains
```

The targeted operator test also initialized a real `PostgresSaver` against the disposable migration database. No VPS, production database, API key, or provider call was used.

## Independent Review Follow-up

A read-only Claude Code review identified three issues in the first retry-lineage draft: concurrent calls could fork attempts, a deleted BYOK configuration could look like an official source, and one runtime-state error message was too broad. The implementation now locks the source execution, allows retry only from a leaf attempt, returns an active child idempotently, enforces a unique `(parent_execution_run_id, attempt_number)` constraint, persists a non-sensitive provider-source marker, and rejects unknown or deleted BYOK sources. Targeted tests cover every one of these cases.

## Known Limits After Default Rollout

- `DOCPILOT_ASSISTANT_ENGINE=operator` is required in production. The deterministic adapter remains for local no-provider operation and contract tests; legacy ReAct is retained only as a compatibility path, not a production engine.
- Operator planning receives at most 12 recent public conversation messages and a bounded authorized memory pack. Optional embedding recall has a short budget and falls back to lexical retrieval rather than delaying the turn.
- Runtime replay is durable finite polling today. Redis fan-out or SSE live subscriptions can optimize latency later but are not needed for correctness.
- The runtime UI exposes cancellation only for eligible workflow bridges. Retry is safe through the execution API and Agent capability, but a visible retry control remains deferred until its project-history UX and permission messaging are designed.
- The old assistant-ui experiment is not the mounted product panel. The mounted panel is the runtime-aware `AIAssistantPanel`; a later UI migration must preserve event, approval, attachment, and recovery semantics instead of swapping visual libraries blindly.
- Full desktop/mobile Playwright visual verification was intentionally not run in this Codex session because the embedded browser is known to destabilize the app. It remains a release gate in a safe browser environment.

## Learning Note

An Agent framework's checkpoint answers: "where can this graph resume?" A product runtime answers: "what happened, who approved it, what domain action was committed, and what should the user see?" Treating checkpoints as product truth is a common prototype mistake. BidPilot now uses checkpoints for execution recovery and PostgreSQL runtime records for business-visible truth.
