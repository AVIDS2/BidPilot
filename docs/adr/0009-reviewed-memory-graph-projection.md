# ADR 0009: Reviewed Memory Graph Projection

- Status: Proposed
- Date: 2026-07-22
- Depends on: ADR 0004, ADR 0005, ADR 0006, controlled MemoryGraphBench

## Context

BidPilot can now create a source-bound, typed entity/relation proposal from one
approved project memory record. Every proposed item is reviewed individually,
the proposal is rechecked against its evidence snapshot before activation, and
the current browser read model intentionally exposes no raw provider output.
A private-manifest capture adapter can also verify that reviewed runtime records
match a frozen benchmark case and emit only synthetic benchmark identifiers and
mapped evidence references for `MemoryGraphBench` scoring.

This is not yet a factual graph. Writing rows into `MemoryEntity` or
`MemoryRelation` prematurely would turn model output into system truth before
we have controlled-corpus quality evidence, a conflict policy, or a measurable
user benefit. It would also create a second unofficial memory system that could
drift from the project evidence and approval history.

## Decision

BidPilot will keep the current graph-proposal and reviewer-decision ledger as
the only graph state until the projection gate below is explicitly approved.
When that gate is met, a future deterministic materializer will create a
**project-local relational projection**, not a graph database and not a new
agent memory authority.

The materializer will have these invariants:

1. It reads only an active graph-proposal memory record whose individual items
   were fully reviewed and whose source/evidence snapshot remains current.
2. It projects only `accepted` items. Rejected items remain audit evidence and
   never become entities or relations.
3. Entity identity is project-local and normalized as `(entity_type,
   canonical_key)`. Relation identity is project-local and normalized as
   `(subject_entity, predicate, object_entity)`.
4. Every projected entity and relation retains exact evidence-link provenance
   to the approved graph proposal and its backing source memory. A relation
   must never inherit unrelated citations merely because it shares a memory
   record with an entity.
5. The operation is idempotent per approved proposal fingerprint and writes a
   durable audit event. Retry after a Worker failure must not duplicate facts.
6. Source deletion, expiry, rejection, supersession, or conflict must make the
   corresponding projection unavailable to the read model. Historical rows may
   be retained for audit, but no stale row is queryable as active fact.
7. All reads stay behind project capability checks. No organization-wide graph
   traversal, public source ids, or browser-supplied graph query is allowed.

The initial materializer will be an explicit owner/approver action or a
governed workflow step. It will not run as an automatic background side effect
of a model result or an ordinary memory approval.

## Projection Gate

Before a migration or materializer can be approved, all of the following must
be retained as reviewable evidence:

1. A small reviewed synthetic/public corpus captured with
   `MemoryGraphBench --require-controlled-capture`; control fixtures are not
   eligible.
2. Perfect schema validity, project-scope isolation, and evidence-reference
   validity in that capture set.
3. Complete reviewer summaries for every captured proposed item, plus recorded
   provider/model/policy/commit and redacted capture provenance.
4. Established precision and recall baselines from that dataset. Thresholds
   must be proposed from observations, not copied from a demo fixture.
5. A concrete user-value experiment showing that a graph read model improves a
   bid decision such as missing requirement coverage or conflict detection
   without increasing unsupported claims.
6. A migration review covering placeholder graph rows, rollback behavior,
   source lifecycle propagation, tenant isolation, and retriable failure paths.

Meeting these conditions authorizes a design review; it does not itself enable
the feature in production. The materializer remains separately feature-gated
until migration, API, worker, audit, and evaluation coverage pass together.

The capture adapter does not classify source material automatically. Operators
must use only reviewed synthetic/public material for graph benchmarks, retain
the private manifest outside the repository, and record the reviewer
attestation in the evaluation provenance.

## Consequences

Positive:

- graph-shaped information remains evidence-backed, reviewable, and reversible;
- no new Neo4j/vector/graph service is introduced before a measured need;
- future retrieval can compare graph assistance against ordinary evidence
  retrieval instead of silently replacing it;
- the project retains a clear interview-grade example of human-in-the-loop
  knowledge projection rather than an ungoverned "AI memory" claim.

Costs:

- users cannot yet query a persistent entity/relation graph as product truth;
- controlled capture and human review require deliberate operating effort;
- a future projection migration will be more constrained than a one-off table
  write, by design.

## Non-Goals

- No automatic user-profile graph.
- No generic graph builder or 3D graph visualizer.
- No graph-derived prompt injection into the Assistant or workflow runtime.
- No claim that `MemoryGraphBench` development fixtures are commercial-quality
  proof.
