# 2026-07-19: Model usage and budget governance

## Objective

Keep platform-funded model usage controllable without exposing provider keys,
prompts, completions, or raw Provider payloads. Request-count trial quotas are
useful but insufficient when multiple concurrent workflows can consume token
capacity before a response is written.

## Implemented

- Added a shared provider-neutral measurement contract for OpenAI-compatible,
  Anthropic, and LangChain usage metadata. It keeps only non-negative numeric
  input, output, reasoning, and cache token counters.
- Added durable organization-scoped `model_usage_record` rows and optional
  official/BYOK monthly token budgets. The control plane creates conservative
  pre-dispatch reservations, then settles actual reported usage, releases
  known non-billable configuration failures, or preserves unknown outcomes as
  short-lived uncertain holds.
- Draft and redraft workflows attach their reservation to both the execution
  run and durable runtime bridge. API preflight is now a generic workflow hold:
  the first real model node claims it as `dispatched`, while every later
  parsing, drafting, review, retry, or checkpoint-replay dispatch receives an
  independently generated hold. A retryable timeout or recovered
  `dispatched` call becomes uncertain, so later success cannot erase a prior
  potentially billable call. The bounded Operator also reserves once for each
  actual planner invocation and commits the hold before network I/O, so it
  never holds a PostgreSQL budget lock while waiting on a model provider.
- Requirement extraction and quality review now use a bounded shared
  OpenAI-compatible/Anthropic structured-text adapter and write their actual
  semantic workload to the ledger. The old LLM supervisor was removed: graph
  routing is deterministic control-plane code, so it cannot spend a model key
  or select an invalid edge.
- Planner inputs are bounded server-side and the assistant LLM factory applies
  an explicit output cap. Native Claude drafting now uses adaptive thinking on
  current official Claude models that reject legacy manual thinking budgets;
  older supported models retain a bounded manual-thinking fallback.
- Account usage data now distinguishes official and BYOK token totals and
  outstanding capacity holds. It deliberately reports cost as unavailable.
- Token-cap changes are restricted to the workspace billing owner and now
  append a minimal organization audit row containing only the before/after
  token limits and actor. Empty or unchanged updates do not create policy or
  audit rows.
- A requested BYOK provider configuration that has been deleted or does not
  belong to the user returns a safe 404 instead of silently falling back to a
  platform-owned provider key.

## Verification

- Alembic head resolves to the new model-usage and budget-event migrations.
- API and Worker compile checks plus Ruff checks passed for the touched paths.
- In-memory targeted ledger, `dispatched` accounting, workflow preflight,
  Operator callback, budget exhaustion, Worker retry/replay reservation,
  structured-provider protocol, and governed-node checks passed without
  contacting a real provider.
- Account-page Vitest, TypeScript check, locale parsing, and production Vite
  build passed.

## Remaining verification boundaries

- A fresh dedicated local `docpilot_test` database was migrated to
  `fa0b1c2d3e4`. Full PostgreSQL regression passed: API `583 passed`, Worker
  `110 passed`. The repository core release rehearsal also passed its migration,
  Ruff, API/Worker test, frontend typecheck, Vitest, and production-build gates.
- The completed local rehearsal does not replace authenticated browser smoke,
  real-provider/VPS traces, quality-gate provenance, or a production-readiness
  check with deployment-shaped secrets.

## Deferred work

1. Add a reviewed provider/model price catalog and invoice reconciliation
   before recording currency or advertising spend caps.
2. Add owner-facing budget editing UI, alert delivery, and an operations view
   for token-budget exhaustion or repeated uncertain holds.
3. Capture real provider and VPS traces with retained release evidence.
