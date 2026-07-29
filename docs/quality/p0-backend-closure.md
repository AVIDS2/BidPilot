# P0 Backend Closure Record

## Purpose

This record defines the backend baseline that the frontend rebuild may consume.
It is deliberately an engineering status record, not a production-availability
claim.

## Verified locally on 2026-07-29

The local Compose stack ran the role-aware acceptance path three independent
times. Each run used a newly created verified actor, organization, project,
buyer-RFP bundle, supplier-evidence bundle, workflow run, review record, and
export artifact.

All three runs completed the same durable path:

```text
buyer RFP + supplier evidence
  -> parse and index
  -> buyer-only Requirement Ledger
  -> retrieve supplier case evidence
  -> link and verify Evidence + factual Claim
  -> readiness coverage update
  -> LangGraph draft
  -> reject -> redraft -> approve
  -> approved-only DOCX export
  -> controlled failed-run retry
```

Observed structural invariants in every run:

| Invariant | Result |
| --- | --- |
| Distinct buyer and supplier bundles | 2 bundles |
| Buyer-sourced Requirement Ledger rows | 32 |
| Supplier-sourced Requirement Ledger rows | 0 |
| Verified requirement coverage | 1 or more covered item |
| Evidence status for mapped requirement | `sufficient` |
| Factual claim status | `verified` |
| Approved export | non-empty DOCX |
| Controlled retry | linked retry run present |

The redacted local receipts remain ignored under `tmp/`; they contain only
opaque identifiers, status values, counts, fixture hashes, and byte counts.
They do not contain raw material, prompts, model output, credentials, or user
content.

## Regression and schema evidence

The following checks passed against the dedicated local `docpilot_test`
database after the role-separation change:

| Check | Result |
| --- | --- |
| Requirement, evidence, readiness, runtime, drafting, export, and rehearsal API regression | 156 passed |
| Retrieval, LangGraph review/resume, runtime event, claim-integrity, and checkpoint Worker regression | 54 passed |
| Assistant Harness, runtime, memory, evaluation, and conversation-access API regression | 267 passed |
| Worker memory, graph, runtime-event, and review-resume regression | 22 passed |
| Alembic health on existing and fresh scratch test databases | 65 / 65 model tables at head `fd2e3f4a5b6c` |
| Development evaluation baseline | 63 fixed control-fixture cases |
| Final full API regression after the role-aware change | 767 passed |
| Final full Worker regression after the role-aware change | 167 passed |
| Final static checks | API Ruff, API mypy (211 source files), and Worker Ruff passed |
| Local platform Assistant SSE smoke | HTTP 200, durable RuntimeRun, Harness turn, streamed response, `completed` terminal state |

The development baseline is intentionally marked `release_eligible: false`.
It proves deterministic regression coverage, not model quality on customer
data or a production accuracy claim.

## Contract available to the frontend

The frontend must consume the API and durable runtime event contracts in
[Backend Contract Freeze For Frontend Rebuild](../architecture/frontend-backend-contract-freeze.md).
In particular:

1. Requirement rows are buyer obligations. Supplier materials are retrievable
   evidence, not requirements.
2. Evidence, Claims, coverage, readiness, reviews, exports, and Runtime Runs
   are server-owned facts.
3. Runtime events are ordered and replayable by `run_id` plus `sequence`.
   Browser state is a projection, never a second workflow state machine.
4. User-visible tool status must use the server-provided safe summary and
   business label. Raw provider responses, internal tool names, payloads,
   checkpoints, object keys, and database identifiers must not be rendered.

## Explicitly not claimed as complete

This closure does not claim any of the following:

- public deployment or a production SLA;
- customer-data validation, legal sufficiency, or bid-award quality;
- a correctly configured public Assistant model for every provider gateway;
- browser UX or visual quality;
- backup/restore on a remote staging environment;
- commercial GA readiness.

Before a public release, run the production readiness and deployment rehearsal
against the actual server configuration, including an authenticated Assistant
turn using the configured platform model. If a provider rejects a configured
model or structured-output option, correct the server-side provider profile or
environment configuration; do not expose the upstream failure to users.

An explicitly selected user BYOK configuration is intentionally not replaced
with the platform model. Its provider, protocol, base URL, model identifier,
and credential must be validated as one configuration when the user saves or
tests it.
