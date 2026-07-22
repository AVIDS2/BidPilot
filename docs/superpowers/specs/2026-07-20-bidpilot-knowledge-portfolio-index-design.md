# BidPilot Knowledge Portfolio Index v1

## Status

- Date: 2026-07-20
- Status: approved implementation slice
- Depends on: governed Bid Wiki, project capability access, Retrieval 2.0

## Problem

BidPilot already has a governed, evidence-backed **Bid Wiki** inside each
project. That is the correct place to inspect source-backed facts, review
proposals, and render an evidence map. It is not enough for a team lead or an
operator who needs to answer three portfolio questions without opening every
project:

1. Which accessible projects have usable shared knowledge?
2. Which projects have proposed knowledge waiting for an authorized reviewer?
3. Which project should I open before asking the Agent a knowledge question?

The answer is not an organization-wide vector search or a decorative global
knowledge graph. Both would confuse discovery with authorization and allow a
model to mix unrelated bid work.

## Product Decision

Add a Workbench-level **Knowledge Portfolio** page at `/knowledge`. It is a
safe index of project knowledge health, with every item deep-linking to the
existing project Knowledge tab:

`/projects/:projectId?tab=knowledge`

It does not duplicate a Wiki, source material, retrieval, or graph rendering.
The project workspace remains the only place where users inspect record bodies,
citations, proposals, compilation detail, and the 2D provenance map.

## Non-Negotiable Data Boundary

The aggregate endpoint is a new public projection. It must not serialize a
`MemoryRecord`, `MemoryContextPack`, `MemoryCompilationRun`, or graph node
directly.

For each visible project it may return only:

- `project_id` and `project_name`;
- active **project-shared** memory count;
- proposed project-shared memory count only when the caller has
  `memory.approve`; otherwise `null`, not `0`;
- the latest project-shared record timestamp;
- a safe latest compilation lifecycle status and timestamp, if one exists.

It must never return or derive:

- memory title, body, structured JSON, citation labels, locators, embeddings,
  content fingerprints, or raw compilation result/error JSON;
- `user_private` records, owner identifiers, or counts;
- `org_shared` records; organization-shared propagation is not enabled;
- a cross-project ranking, semantic similarity result, or context pack;
- deleted-project data.

Expired records are also excluded from readiness and review counts because they
cannot enter a current authorized memory context.

Counts are discovery metadata, not model context. The Agent cannot take this
endpoint as permission to retrieve a project's knowledge.

## Authorization Contract

1. Resolve the caller's active organization first.
2. Start from `list_accessible_projects`, which excludes deleted projects and
   enforces membership for non-admin callers.
3. A project appears only when the caller has project membership/admin access;
   every current project role has `memory.read`, so the summary mirrors the
   project Knowledge tab visibility.
4. Proposed count is calculated only for projects where the caller has
   `memory.approve`; callers without that capability receive `null`.
5. The query filters `MemoryRecord.scope == project_shared` in SQL. It does not
   enumerate private records and then filter them in Python or the browser.
6. The individual `GET /memory` project path keeps two explicit sources:
   project-shared records and the requesting user's own project-private
   preferences. A teammate's private preference is never a shared Wiki row.

The API is bounded newest-first and uses grouped/correlated aggregate queries.
It must not issue one memory request per project from the browser.

## API Shape

`GET /memory/portfolio?limit=50`

```json
{
  "items": [
    {
      "project_id": "...",
      "project_name": "Airport Terminal Bid",
      "active_shared_count": 18,
      "proposed_shared_count": 3,
      "latest_shared_memory_at": "2026-07-20T08:00:00Z",
      "latest_compilation_status": "succeeded",
      "latest_compilation_at": "2026-07-20T07:55:00Z"
    }
  ]
}
```

`proposed_shared_count` is nullable. The API never uses an omitted/zero value
to imply a caller has permission to inspect proposals.

## User Experience

The page answers operational questions with real data:

- a compact portfolio summary of active shared knowledge and reviews waiting
  for the current user;
- local filters: all, ready knowledge, needs review, no shared knowledge;
- a project list/card that communicates evidence-backed knowledge status,
  latest maintenance time, and an explicit **Open Bid Wiki** action;
- a clear empty state that directs a user to select a project and compile
  parsed source material.

It does not show a cross-project graph. The existing React Flow map remains
project-scoped because every displayed relation must stay traceable to a
project source and its capability boundary.

### Agent Behavior

The Agent uses the read-only `list_knowledge_portfolio` tool to answer
questions such as "which of my projects need Wiki review?". The tool returns
this same safe projection only. For a substantive question, the Agent must ask
the user to select a project (or use explicit current project context) and then
call the existing project-authorized `search_bid_wiki` path.

No global portfolio result is injected into a LangGraph prompt. Checkpoint
state remains thread-scoped, and a project-authorized `MemoryContextPack`
remains the only long-term memory input to work execution.

## Delivery and Test Gates

### Backend

- repository query covers only active organization + accessible non-deleted
  projects;
- project-shared active/proposed counts are SQL-filtered by scope and status;
- a member cannot discover an inaccessible project's name, counts, compilation
  state, or private-memory existence;
- a viewer receives `null` proposal count while an approver sees the count;
- response schema has no title/body/citation/owner/vector/JSON fields.

### Frontend

- `/knowledge` uses one bounded aggregate request and deep-links to the
  project Knowledge tab;
- empty, narrow desktop, and mobile layouts do not overflow or collapse;
- no fake data, no client-side aggregation of project-memory records, and no
  global graph canvas.

### Agent

- the delivered portfolio tool is read-only and provides no project knowledge
  content;
- selection of a project is required before `search_bid_wiki` or context-pack
  retrieval;
- tests prove that a portfolio response cannot cause cross-project recall.

## Explicit Deferrals

- organization-wide automatic memory writes;
- 3D graph rendering;
- cross-project semantic search or global RAG;
- using personal preferences as team Wiki content;
- treating LangGraph Store or checkpoints as the memory ledger source of truth.

## References

- [BidPilot Governed Memory and Bid Wiki Design](2026-07-17-bidpilot-governed-memory-wiki-design.md)
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph stores](https://docs.langchain.com/oss/python/langgraph/stores)
- [LangChain long-term memory](https://docs.langchain.com/oss/python/langchain/long-term-memory)
