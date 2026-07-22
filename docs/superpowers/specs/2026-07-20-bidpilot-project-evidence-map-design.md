# BidPilot Project Evidence Map v1

## Status

- Date: 2026-07-20
- Status: implemented bounded projection
- Depends on: governed Bid Wiki, project capability access, Knowledge Portfolio

## Problem

The project Knowledge tab currently renders a small React Flow diagram by
joining the browser's already-loaded memory records and citations. It is useful,
but it is not a durable graph contract:

- the backend has no explicit, bounded Evidence Map projection;
- `memory_entity` and `memory_relation` tables exist, but no compiler writes
  them yet;
- a client-side graph can accidentally drift from the access, expiry, and
  source-traceability policy used by the memory ledger;
- calling the current map a "knowledge graph" would overstate what it proves.

## Research Decision

Microsoft GraphRAG distinguishes entity/relation extraction from later graph
exploration and reports that graph extraction is a major indexing cost. Its
FastGraphRAG alternative is cheaper but noisier for graph exploration. BidPilot
therefore does **not** introduce speculative LLM entity extraction merely to
populate a visual graph. Every visual node must first be traceable to an active
project-shared memory record and a validated source link.

Sigma.js plus Graphology remains the future large-graph renderer candidate. Its
official documentation positions it as a WebGL renderer for thousands of
nodes. The initial Evidence Map is deliberately bounded to a small,
business-readable project scope, so the existing React Flow dependency remains
the simpler and more appropriate renderer today.

## Product Decision

Add an explicit project-scoped `Evidence Map` API and make the Knowledge tab
consume it. It is a provenance projection, not a general GraphRAG endpoint.

It answers one operational question:

> Which currently active, shared Bid Wiki entries cite which project sources?

The map helps a reviewer inspect evidence coverage before opening a specific
knowledge record. The ledger remains the source for body text, citations,
proposals, review actions, and compilation detail.

## Data Boundary

`GET /memory/evidence-map?project_id=...` must:

1. require `memory.read` on exactly one project;
2. read only active, non-expired, non-deleted `project_shared` records;
3. return a bounded set of record nodes, source nodes, and `cites` edges;
4. use server-derived citation labels only;
5. return opaque graph node ids rather than raw source ids;
6. set `truncated` when bounded data was omitted.

It must never return:

- user-private, organization-shared, proposed, rejected, superseded, expired,
  or deleted memory records;
- record bodies, structured JSON, embeddings, content fingerprints, source
  chunk text, raw locators, provider metadata, or graph compiler internals;
- another project's data, even if a caller is a member of the same
  organization;
- an entity/relation inferred by an LLM without explicit review and a source
  trace.

The API schema is a fresh public projection. It does not serialize ORM memory
or relation models directly.

## Graph Semantics

```text
[active shared memory] -- cites --> [validated project source]
```

The edge predicate is deliberately `cites`, not `supports` or `proves`.
Citation is a traceability relationship; factual sufficiency remains a
Requirement Ledger and human-review question.

Node labels are permitted project-local labels:

- memory node: active shared record title and kind;
- source node: server-canonical citation label and source type.

No node carries raw source identifiers in the public graph response. A future
source-opening action must use a separate capability-checked endpoint.

## UI Behavior

- The project Knowledge tab fetches the ledger and Evidence Map separately.
- Ledger rows can still show authorized proposed items, but the map visualizes
  active shared knowledge only.
- A map loading, empty, error, and truncation state are explicit. The browser
  never invents or joins a hidden graph locally.
- React Flow stays in read-only mode for this bounded map. It is not a workflow
  editor and it is not the eventual large-scale knowledge explorer.
- The Agent may refer a user to the project Knowledge page, but no Evidence Map
  result is silently injected into Agent or workflow model context.

## Entity Graph Deferral

`MemoryEntity` and `MemoryRelation` are reserved for a later projection built
from reviewed structured proposals. That work requires all of the following:

1. a typed extraction schema with canonicalization and source citations;
2. a human approval policy for factual relations;
3. frozen evaluation fixtures for precision, duplicate merging, contradiction,
   project isolation, and stale-node removal;
4. measurable evidence that graph exploration improves a real BidPilot user
   decision;
5. a scale threshold that justifies evaluating Graphology and Sigma.js.

Until those gates pass, a 3D view would be decorative and may mislead reviewers
about the confidence of extracted facts.

## Acceptance Criteria

- a member can only retrieve their accessible project's active shared graph;
- a viewer cannot infer private/proposed/expired record existence;
- an edge never points to a missing returned node;
- graph nodes contain no record body, raw source id, locator, vector, or model
  metadata;
- the Knowledge tab renders server-projected nodes and edges, not a client-side
  record/citation join;
- API, component, and authorization tests cover populated, empty, and denied
  cases;
- no new graph-rendering dependency is added for this bounded slice.

## Implementation Record

- `GET /memory/evidence-map` now performs the authorization and lifecycle
  filtering on the server before it returns a bounded `memory -> cites ->
  source` projection.
- Source graph identifiers are opaque digests; the public response contains no
  record body, raw source identifier, locator, vector, or model metadata.
- The Knowledge tab separately queries the ledger and map. It explicitly
  renders loading, empty, error, and truncation states instead of rebuilding a
  graph from browser-resident citations.
- The implementation intentionally retains React Flow for the current bounded
  project view and adds no large-graph dependency.

## References

- [Microsoft GraphRAG indexing dataflow](https://microsoft.github.io/graphrag/index/default_dataflow)
- [Microsoft GraphRAG methods and cost trade-offs](https://microsoft.github.io/graphrag/index/methods)
- [Sigma.js documentation](https://www.sigmajs.org/docs)
- [BidPilot Governed Memory and Bid Wiki Design](2026-07-17-bidpilot-governed-memory-wiki-design.md)
