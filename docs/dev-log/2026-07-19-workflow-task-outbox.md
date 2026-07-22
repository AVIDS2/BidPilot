# 2026-07-19: Transactional workflow task Outbox

## Objective

Make billable drafting workflow delivery recoverable across the API transaction,
Celery broker publish, Worker restart, and duplicate broker-delivery boundaries.

## Implemented

- Added `task_outbox_event` with an Alembic migration. It stores only trusted
  task metadata, durable run references, lease state, counters, and safe error
  codes; provider keys, prompts, completions, and raw provider payloads are
  excluded.
- Normal draft, redraft, explicit retry, and LangGraph human-resume requests
  now persist their task intent in the same transaction as execution state,
  runtime state, reservations, usage, and audit evidence. The API wakes the
  dispatcher only after commit.
- Worker dispatch uses short database leases and a minutely Beat recovery scan.
  The task consumer claims a longer delivery lease before execution, completes
  on a handled terminal result, and records a safe terminal failure code when
  the task raises.
- The event producer converts a concurrent unique-key collision into a read of
  the existing logical event inside a savepoint, preserving the caller's wider
  workflow transaction rather than surfacing a duplicate-delivery error.
- Human resume now accepts only an `awaiting_human` execution run and writes a
  monotonic `resume_sequence` in the same transaction. This prevents a repeated
  browser request from producing a second resume delivery while still allowing
  a later graph pause to resume with a new event.
- The Outbox defers the Celery import to publish time. That breaks a real
  circular import between Celery task autodiscovery, `app.tasks`, and the
  Outbox consumer module.

## Verification

- `uv run --directory services/api alembic heads` reports
  `fa0b1c2d3e4 (head)`.
- API/Worker Ruff and `compileall` pass for the Outbox producer, consumer,
  wrapper tasks, migrations-adjacent tests, and related command services.
- Isolated SQLite manual checks passed for post-commit API wake-up, sequenced
  human resume, dispatcher publication, Beat recovery, duplicate consumer
  rejection, and failure persistence.
- Full PostgreSQL regression now passes on a freshly migrated local
  `docpilot_test` database: API `583 passed`, Worker `110 passed`. The core
  repository release rehearsal also passed its API/Worker static checks, tests,
  frontend typecheck, Vitest, and production build.

## Residual boundary

This gives at-least-once internal task delivery, not exactly-once external
model invocation. If a worker dies after a provider accepted a request but
before LangGraph checkpoints that node, replay can issue another provider call.
The model-usage lifecycle conservatively retains/records the ambiguous prior
attempt; exact provider-side idempotency requires a provider-supported key or a
future durable node-result protocol.

## Remaining verification boundary

No production database, server state, authenticated browser flow, real provider
call, or VPS trace was modified or asserted by this implementation.
