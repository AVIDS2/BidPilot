# BidPilot Reviewed Entity and Relation Projection v1

## Status

- Date: 2026-07-22
- Status: controlled extraction, per-item review, and redacted runtime capture implemented; persistent graph projection remains gated
- Depends on: governed Bid Wiki, project capability access, Evidence Map v1,
  MemoryGraphBench

## Product Question

An evidence map answers **which approved Bid Wiki entry cites which source**.
It does not answer **which real-world things and obligations are related**, nor
does it prove a model's extracted relation is correct. BidPilot needs a path to
turn source-grounded project knowledge into a useful review surface without
turning a visual graph into unreviewed factual authority.

The intended user outcome is narrow and practical:

> A bid manager can inspect a reviewed relationship such as “this requirement
> requires this deliverable” and open the exact project evidence that supports
> it before relying on it in a response.

## Research Constraints

- [LangGraph memory](https://docs.langchain.com/oss/python/langgraph/add-memory)
  separates thread-scoped checkpoint state from cross-thread long-term memory.
  BidPilot retains PostgreSQL memory records as product truth; graph data is a
  projection, not LangGraph state.
- [LangMem's conceptual guide](https://langchain-ai.github.io/langmem/concepts/conceptual_guide)
  treats semantic memory as an extraction and consolidation problem and warns
  that over-extraction reduces precision while under-extraction reduces recall.
  A graph proposer is therefore not a truth writer.
- [Microsoft GraphRAG's dataflow](https://microsoft.github.io/graphrag/index/default_dataflow)
  extracts entities and relationships from text units, merges them, then
  summarizes them. Its [methods guide](https://microsoft.github.io/graphrag/index/methods)
  reports graph extraction as a major indexing cost and calls the cheaper fast
  method noisier for graph exploration. BidPilot will measure the use case
  before paying that cost or promising a graph explorer.

## Architecture Decision

The graph has four separate layers:

```text
validated source links
        -> reviewed MemoryRecord
        -> typed MemoryGraphProposal (proposed)
        -> per-item reviewer decision ledger
        -> approved materialized entity/relation projection
        -> bounded visual/retrieval read model
```

No layer may skip the one before it. In particular, a model cannot create a
permanent entity or relation simply because a prompt returned valid JSON.

### Implemented foundation

`packages/contracts/memory_graph.py` defines the proposal boundary:

- a small bid-domain entity type vocabulary;
- a small relationship predicate vocabulary;
- stable local ids and normalized semantic entity keys;
- unique entity and relation semantics;
- evidence source references for every entity and relation;
- no rationale, hidden reasoning, prompt, provider payload, or raw source
  text field.

An optional `memory_graph_proposal` nested payload can only enter a
project-shared `entity_note` memory proposal. The API resolves user citations
first, then rejects graph items that cite anything outside those canonicalized
typed source references. It still enters the existing review queue as a proposal.

`MemoryGraphBench` evaluates captured outputs offline. It records only opaque
case ids, scope identifiers, entity names/types, predicates, typed evidence
references, extractor policy, optional provider/model/latency/cost metadata,
redacted capture provenance, and aggregate reviewer-decision counts. It does
not execute an LLM or connect to production data.

### Redacted Runtime Capture Adapter

`services/api/app/evaluation/memory_graph_runtime_capture.py` converts an
already-reviewed workflow record into one `MemoryGraphBench` candidate. Its
private manifest maps each frozen benchmark case to the durable proposal,
source-memory, execution-run, and source-evidence ids used during the real
controlled run. The manifest is an operator-only input and must never be
committed or copied into an evaluation artifact.

Before exporting a case, the adapter verifies that:

- every frozen benchmark case has exactly one capture mapping;
- the source is active, project-shared, non-expired memory and the proposal is
  a current `entity_note` with the same source snapshot and policy version;
- one successful graph-extraction `ExecutionRun` and one successful,
  scope-matching `workflow_bridge` RuntimeRun are linked to the proposal;
- every durable review decision matches the proposal fingerprint, organization,
  project, and typed item; and
- the private evidence map exactly covers the proposal evidence and maps only
  to evidence references already frozen in the benchmark case.

The generated candidate substitutes benchmark case/org/project/memory ids and
mapped benchmark evidence ids. It never writes durable runtime ids, source ids,
source titles, bodies, citation labels, locators, provider payloads, or model
reasoning into the output. Entity and relation names remain in the candidate
because the scorer needs them; therefore the mapped source material must be
synthetic or approved public data. The required CLI acknowledgement records an
operator attestation, not an automatic data-classification guarantee.

## Controlled Extraction Capture

The first model-backed path is intentionally one source record at a time. It
uses the same product-owned execution, runtime, quota, model-usage, audit, and
durable Outbox contracts as other billable workflows; it is not a browser-side
prompt or an untracked background task.

1. A user with both `memory.approve` and `workflow.run` selects one active,
   non-expired `project_shared` record with validated evidence.
2. The API fingerprints the record's title, body, typed source references, and
   policy version. A durable Outbox key is unique for that project/source/
   fingerprint tuple.
3. Execution run, Runtime bridge, model-capacity reservation, usage event,
   audit event, and Outbox event commit atomically. Repeated clicks return the
   already queued/running/completed attempt without another reservation or
   provider call.
4. A terminal failed attempt may create a linked child attempt for the same
   unchanged source snapshot. That new physical call gets a fresh reservation
   and usage record; the prior failed attempt remains auditable.
5. The Worker gives the provider only the approved memory title/body and
   validated citation labels/typed references. It validates the typed response
   and rechecks the source snapshot after provider dispatch. A changed source
   discards the result instead of attaching a stale proposal.
6. A successful result becomes only a proposed `entity_note` MemoryRecord.
   It clones the validated source links as `derived_from` evidence and writes
   no `MemoryEntity` or `MemoryRelation` row.

The Knowledge tab exposes this request only to approvers. It renders the
returned entities, relations, opaque per-item review ids, and their
human-readable evidence labels from a safe typed read model. It does not return
raw model payloads, internal provider diagnostics, hidden reasoning, local ids,
or a generic `structured_data_json` blob.

## Proposal Contract

One `MemoryGraphProposal` has this shape conceptually:

```json
{
  "schema_version": "bidpilot.memory-graph/v1",
  "entities": [
    {
      "local_id": "private_deployment",
      "canonical_name": "私有化部署",
      "entity_type": "requirement",
      "evidence_refs": [
        {"source_type": "knowledge_chunk", "source_id": "<validated-source-id>"}
      ]
    }
  ],
  "relations": [
    {
      "subject_local_id": "private_deployment",
      "predicate": "requires",
      "object_local_id": "proposal",
      "evidence_refs": [
        {"source_type": "knowledge_chunk", "source_id": "<validated-source-id>"}
      ]
    }
  ]
}
```

The current v1 vocabularies are intentionally constrained:

- entity types: bidder, issuer, bid project, requirement, qualification,
  deliverable, deadline, standard, document, location, amount, and risk;
- predicates: applies to, conflicts with, depends on, has deadline, issued by,
  requires, requires evidence, references, and submitted by.

An extractor may omit a relationship when the text is ambiguous. It may not
invent a generic relation name or attach a source that was not part of the
memory record's authorized evidence.

`confidence` is optional diagnostic routing metadata. It is never a truth
score and must not be rendered as evidence sufficiency to users.

## Review and Lifecycle

1. A future graph compiler receives only a bounded, authorized set of active
   project-shared memory records and their already validated source links.
2. It produces a typed proposal attached to a `MemoryRecord` with status
   `proposed`; it does not write graph rows.
3. A user with `memory.approve` sees entities, relations, and source labels,
   then accepts or rejects each item through an opaque server-generated id.
   Every decision is tenant- and project-scoped, bound to a canonical proposal
   fingerprint, and written to both memory and project audit trails.
4. A graph proposal cannot be enabled while an item is still pending. Once it
   is enabled, the item-decision snapshot is frozen. For Worker-generated
   proposals, final enablement recomputes the source memory/evidence snapshot;
   an inactive, expired, deleted, or changed source requires regeneration.
5. Review acceptance still does **not** materialize `MemoryEntity` or
   `MemoryRelation` rows. Only a future explicit materializer, after its
   quality gate, may do that.
6. Deleting, expiring, rejecting, or superseding a backing record removes its
   contribution from the read model. Contradictory records stay visible as a
   review conflict rather than silently overwriting an earlier relation.

The materializer must be idempotent on `(memory_record_id, proposal schema
version, normalized semantic key)`. It must write an audit event and be safe to
retry after a Worker crash.

## Future Persistence Model

The existing `MemoryEntity` and `MemoryRelation` tables were created as a
placeholder and are not currently written. Before materialization ships, the
following migration must be reviewed:

| Concern | Required shape |
| --- | --- |
| Entity identity | project-local `(entity_type, canonical_key)` identity, with deterministic Unicode/whitespace normalization; aliases are metadata, not authorization keys |
| Entity provenance | a many-to-many entity-to-memory-evidence table; one entity may have several approved sources |
| Relation identity | project-local `(subject, predicate, object)` identity, separate from the source record that first introduced it |
| Relation provenance | a many-to-many relation-to-memory-evidence table so one relation never inherits unrelated citations from the same memory body |
| Lifecycle | active, superseded, deleted, and conflict/review state must be derived from backing approved records and never outlive them |
| Tenant boundary | every identity, relation, and evidence row carries organization and project scope and is queried through `memory.read` / project capability checks |

The migration must preserve any existing placeholder data or explicitly fail
with a reviewed migration report. It must not delete duplicate entities merely
to satisfy a uniqueness constraint.

## Agent and Retrieval Policy

- The Assistant may create a **proposed** graph extraction task only after the
  user has selected a project and the normal provider, quota, and approval
  controls pass.
- The Agent must never query arbitrary graph rows as implicit truth. Until a
  dedicated ablation proves value, normal drafting continues to use the
  governed MemoryContextPack and source retrieval contracts.
- Graph-derived answers must expose their backing memory/source links and
  degrade to standard evidence retrieval if the graph is absent, stale, or in
  conflict.
- Cross-project graph search, organization-wide automatic consolidation,
  public source ids, and a 3D graph renderer remain out of scope.

## MemoryGraphBench

The visible synthetic development fixture lives at:

```text
benchmarks/bidbench/v1/demo-smart-community/memory-graph-development.json
```

The runner accepts a captured, redacted proposal result and reports:

- schema validity;
- scope isolation pass rate;
- entity precision and recall;
- relation precision and recall;
- evidence-reference validity;
- grounded relation recall, where a semantically matched relation shares at
  least one expected evidence reference.

Run it without calling a provider:

```powershell
uv run python scripts/run_memory_graph_bench.py `
  --dataset benchmarks/bidbench/v1/demo-smart-community/memory-graph-development.json `
  --run <captured-graph-proposal-run.json>
```

The captured run and output reports stay under ignored `output/`; committed
fixtures must be synthetic or approved public data only.

Create a real candidate from a private local manifest without calling a model:

```powershell
uv run python scripts/capture_memory_graph_runtime_bench.py `
  --dataset benchmarks/bidbench/v1/demo-smart-community/memory-graph-development.json `
  --manifest <private-redacted-capture-manifest.json> `
  --confirm-redacted-graph-capture `
  --output-file output/memory-graph-runtime-capture/candidate-run.json
```

Then score the redacted output with `--require-controlled-capture`. Keep the
manifest in approved release storage outside the repository; it contains
durable database references even though the generated run does not.

For a real controlled capture, add `--require-controlled-capture`. The runner
then requires a Git commit, provider and model metadata, non-control provenance,
and a complete, count-consistent per-item review summary. It also rejects any
schema, scope, or evidence-validity miss. This is **baseline eligibility only**:
it intentionally does not set precision/recall thresholds or claim a release or
materialization decision.

## Rollout Gates

### Gate A: contract and measurement

Complete now. Invalid shapes, missing endpoints, duplicate canonical entities,
and unavailable source references are rejected. A synthetic fixture and
offline scorecard exist.

### Gate B: controlled extraction capture

The governed one-record extraction path, per-item reviewer decisions,
proposal/source evidence recheck, fail-closed capture-readiness contract, and
private-manifest-to-redacted-run adapter are implemented. Next, execute it on a
small reviewed synthetic/public corpus and one low-cost model at a time. Retain
the private manifest, generated candidate, scored report, policy version,
model/provider metadata, and reviewer attestation in controlled release
storage. The visible development fixture cannot satisfy this gate by itself.
Do not materialize production rows yet.

### Gate C: persistence pilot

Approve a migration and a deterministic materializer only after the captured
set shows no scope leak and no invalid evidence references. Establish actual
precision/recall baselines first; hard release thresholds should be set from
that reviewed dataset, not guessed from one demo project.

### Gate D: product value experiment

Compare a reviewer completing a concrete bid task with standard evidence
retrieval versus the graph read model. Proceed only if the graph improves a
measurable decision such as missing requirement coverage or conflict detection
without increasing unsupported claims.

## Non-Goals

- No Neo4j or additional graph database service.
- No automatic background memory/graph activation.
- No graph-as-authority prompt injection.
- No hidden chain-of-thought storage.
- No unbounded user profile or organization knowledge graph.
- No decorative 3D visualization before a credible, dense, reviewed graph
  warrants it.

## Acceptance Criteria for the Next Code Slice

1. A controlled extraction can create only a source-bound `proposed` graph
   memory record and does not double-reserve model capacity for the same
   source snapshot.
2. A reviewer can inspect and accept/reject every entity and relation through
   a source-safe item id before activation.
3. The final activation rechecks the Worker source snapshot and freezes review
   decisions; relation-level review is not a capability silently implied by the
   proposal renderer.
4. Materialization is idempotent and retains exact evidence links per entity
   and relation.
5. Lifecycle transitions remove stale projections and preserve audit history.
6. Graph API authorization mirrors project memory authorization.
7. The new extraction path is evaluated through MemoryGraphBench before and
   after any prompt, model, or canonicalization change.
