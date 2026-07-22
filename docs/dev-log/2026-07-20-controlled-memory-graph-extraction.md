# Controlled Memory Graph Extraction

## Why This Slice Exists

The repository had a typed graph-proposal contract and an offline scorecard,
but no product path that could create a proposal under the same governance as a
billable workflow. A direct model-to-graph write would have bypassed review,
usage accounting, and the established source-of-truth boundary.

## Delivered Boundary

- Added a source-bound `POST /memory/graph-extractions` command for active,
  evidence-backed project knowledge only.
- The command requires `memory.approve` and `workflow.run`, creates a normal
  ExecutionRun and Runtime bridge, reserves model capacity, records usage and
  audit data, and dispatches through the durable task Outbox.
- A deterministic project/source/snapshot Outbox key makes duplicate clicks
  return the same live or completed run without another model reservation.
  Only a terminal failed attempt can create an auditable child retry.
- The Worker rechecks title/body/evidence snapshot before and after provider
  dispatch, validates the typed proposal against authorized evidence, and
  persists only a proposed `entity_note` plus cloned `derived_from` citations.
- The Knowledge tab exposes a narrowly typed reviewer read model: entities,
  relations, and evidence labels. It does not send raw structured data, model
  output, confidence values, prompts, or hidden reasoning to the browser.
- Added `memory_graph_review_decision` as a per-item audit ledger. The browser
  receives only opaque item ids, user-facing names, evidence labels, and
  `pending` / `accepted` / `rejected` state; it never receives proposal local
  ids or raw provider output.
- A `memory.approve` user can accept or reject individual entities and
  relations. Each decision is bound to a canonical proposal fingerprint and is
  recorded in the memory and project audit trails. A graph proposal remains
  blocked from overall activation until every item has a decision, and its
  decisions freeze after activation.
- Worker-generated proposals recheck their original active shared-memory
  source and all evidence links at activation time. Any source deletion,
  expiry, policy mismatch, or snapshot drift blocks activation and requires a
  fresh extraction.

## Activation Hardening

- Approval and per-item decision commands lock the proposal row, so a reviewer
  who observed `proposed` cannot commit a late decision after another reviewer
  activates it.
- Activation revalidates the proposal's own evidence envelope and, for
  Worker-backed proposals, locks and rechecks the active source record plus its
  evidence links in the same transaction. Invalid payloads, removed proposal
  evidence, stale policy, and source-snapshot drift all fail closed with a
  regeneration request.
- `MemoryGraphBench` now preserves redacted provider/model/cost/provenance
  metadata and aggregate reviewer-decision counts. Its optional
  `--require-controlled-capture` mode refuses a false-green baseline unless all
  graph items have a valid completed review and schema/scope/evidence safety is
  perfect. It deliberately does not invent precision/recall thresholds.

## Explicit Non-Claims

- No entity/relation table materialization.
- No graph retrieval injected into Agent or Workflow context.
- No entity/relation table materialization, graph retrieval, or graph facts in
  Agent context. The review ledger is not a graph database.
- No automatic graph approval, cross-project consolidation, graph database,
  or decorative 3D graph explorer.

## Verification

- API memory command coverage: `17 passed` using the self-contained API test
  environment, including per-item review, evidence-envelope rejection,
  activation freeze, and source-snapshot drift rejection.
- MemoryGraphBench coverage: `9 passed`, including redacted capture provenance,
  reviewer-summary coverage, and false-green capture rejection.
- Worker graph adapter/extraction coverage: `4 passed` using self-contained
  SQLite fixtures; the normal Worker suite remains guarded until an explicit
  `_test` database URL is supplied.
- Knowledge tab coverage: `5 passed`; frontend TypeScript passed.
- PostgreSQL Alembic head contains the review-decision table and its dedicated
  migration assertion passes on `docpilot_test`.
- Targeted API and Worker Ruff checks passed.

## Next Gate

Run controlled low-cost captures against a reviewed synthetic/public corpus,
record reviewer decisions, and score each capture with
`--require-controlled-capture`. Use that evidence to establish real baselines
before designing the evidence-link-preserving materialization migration; do not
turn the review ledger into production graph facts without it.
