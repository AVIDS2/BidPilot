# BidPilot Interview Golden-Path Script

Use this script to demonstrate the engineering decisions behind BidPilot in
10 to 15 minutes. It is intentionally a traceable workflow demo, not a claim
that one prompt can autonomously replace bid professionals.

## Demo contract

**Problem:** A bid team needs to turn a tender and supplier material into a
reviewable response without losing provenance, authorization or accountability.

**System rule:** PostgreSQL owns business truth. Model output, browser state and
LangGraph checkpoints are execution inputs or projections, never the source of
truth for approval, project access, or final export.

**Safe fixture:** [`sample-data/bidpilot-demo`](../../sample-data/bidpilot-demo)
is synthetic and public-safe. Do not use a real procurement in an interview.

## 0. Architecture overview (one minute)

Show the diagram in the root [README](../../README.md), then state the two
runtime boundaries:

1. **Pi Agent sidecar + API control plane** own interactive product actions.
   Pi chooses provider-native tool calls; every call crosses API capability
   policy, authorization, audit and event persistence.
2. **Celery + LangGraph** owns long-running bid work. It starts from durable
   IDs and version snapshots, pauses at human review, and resumes using the
   same `ExecutionRun` checkpoint scope.

The key design decision is that the Harness is not another public LangGraph
endpoint. It bridges to a worker workflow when the work is long-running.

## 1. Create and inspect a project (two minutes)

Create the synthetic demo project. Then ask the Assistant:

> 查看这个项目的资料、需求和运行状态，再告诉我下一步。

**Show:**

- the visible Assistant timeline;
- a `RuntimeRun` with monotonic `RuntimeEvent` records;
- a user-facing capability summary, not raw tool JSON;
- the replay behavior: the same `client_request_id` is one durable run, rather
  than two messages/model calls/tool executions.

**Explain:** reads may run directly in `risky_only` mode, but a write/costing
action gets a durable approval. Approval does not grant access; project
membership is still checked in the domain service.

## 2. Ingest evidence (two minutes)

Upload the synthetic RFP, supplier capability and case-study files. Explain
that Assistant attachments first live in private staging and only enter project
knowledge through an authorized ingestion capability.

**Show:** document parse/index state, requirement records, evidence locators,
and the requirement ledger. Point out a requirement that has no valid
supporting source; the correct answer is a gap, not an invented claim.

## 3. Bridge from Harness to workflow (three minutes)

Ask:

> 基于已验证资料起草“技术响应方案”章节；若缺资料请先告诉我缺什么。

Confirm the action when requested.

**Show:**

1. the Assistant parent `RuntimeRun`;
2. the linked `RuntimeRun(kind=workflow_bridge)` and `ExecutionRun`;
3. durable worker progress/replay events rather than a browser-only spinner;
4. the LangGraph phase: scoped evidence -> response plan binding -> draft
   candidate -> validation -> review interruption or persistence.

**Explain:** the graph input is stable IDs and version bindings. A checkpoint
helps resume execution, but review decisions and immutable versions live in
PostgreSQL. This prevents a replay from silently replacing an approved draft.

## 4. Human-in-the-loop and export (three minutes)

Reject the first candidate with a concrete request, then start a redraft and
approve the later version. Finally export the deliverable.

**Show:**

- both `SectionVersion` records and their review decisions;
- the worker resume triggered only after the review transaction commits;
- an export that reads approved-version snapshots only;
- the audit trail proving who approved and exported what.

**Explain:** this is where the system differs from a generic document chatbot:
it keeps version, evidence, human authority and final delivery connected.

## 5. Failure and recovery narrative (two minutes)

Use this real engineering incident, not a fabricated success story:

> An Assistant request once failed with `UndefinedTable` for
> `assistant_action_audit`. The immediate symptom was a normal product action
> failing because application code expected a table that the target database had
> not migrated.

Root cause: application/model evolution was not being proved against both an
existing database and an empty database at the current Alembic head.

Fix:

1. Keep the table in Alembic migration
   `a4b5c6d7e8f9_add_assistant_audit_tables.py`.
2. Add `scripts/verify_migration_health.py`, which upgrades a dedicated test
   database and a generated scratch database, then verifies the current head
   and ORM tables.
3. Make migration health, Ruff and mypy real CI blockers. The CI no longer
   masks type/lint failures with `|| true` and installs the locked UV workspace
   once before running service-specific commands.

**Show:** the migration-health command in CI and the safe runtime diagnostics
view. Explain that raw SQL/provider exceptions are not sent to end users; the
operator sees a stable error class and run correlation instead.

## 6. Evaluation honesty (one minute)

Show the development baseline receipt generated by
`scripts/run_development_baseline.py` if it is available. State precisely:

- it covers fixed retrieval, memory, Assistant and bid regression cases;
- it records code/data fingerprints and report checksums;
- it is currently a deterministic `control_fixture`, marked
  `release_eligible: false`;
- it is evidence of contract/regression reliability, not a claim that a live
  provider has reached commercial bid-writing quality.

The next release claim requires a reviewed frozen set, a deployed acceptance
run and a backup/restore drill.

## Questions to expect

| Question | Direct answer |
| --- | --- |
| Why not make everything LangGraph? | The public Assistant needs a small, auditable request/replay loop. LangGraph is used where long-running branching, checkpoints and human interrupts justify it. |
| How do you prevent duplicate work? | User-scoped `client_request_id` idempotency resolves to one `RuntimeRun`; workflow persistence uses stable run/version keys and outbox delivery. |
| How do you prevent hallucinated bid claims? | Drafting reads scoped evidence sets and source locators; unsupported assertions become missing-evidence/gap states and final export is approval-gated. |
| What is the security boundary? | Server authorization, project membership, capability policy, encrypted provider-key handling, redacted events/errors, and approved-content-only export. |
| What remains before commercial release? | Live-provider evaluated quality, production rehearsal, backup/restore evidence, user acceptance, support and compliance operations. |

## Evidence checklist

- [ ] `RuntimeRun`, `RuntimeEvent`, approval and workflow bridge visible.
- [ ] `ExecutionRun` / SectionVersion / review decision linkage visible.
- [ ] Source locators and a missing-evidence outcome visible.
- [ ] An approved-only export record visible.
- [ ] One failure has root cause, regression and operator-safe diagnostic path.
- [ ] No real customer material, secrets, opaque IDs or raw provider failures
  are exposed during the demo.
