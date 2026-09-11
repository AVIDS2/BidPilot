# BidPilot Governed Memory and Bid Wiki Design

- Status: accepted for staged implementation; product control plane remains incomplete
- Date: 2026-07-17
- Depends on: ADR 0001, ADR 0005, Retrieval 2.0, project capability access

## 2026-09-09 product decision

The engineering model uses four memory types, but the product must not expose
four memory pages or use Mem0 as a general-purpose memory database.

| Type | BidPilot mapping | Durable owner | First release rule |
| --- | --- | --- | --- |
| Working | current project/session/task context | Pi session, ChatMessage, RuntimeRun/Event | never promoted automatically to long-term memory |
| Episodic | completed work, review decisions, failures, corrections | PostgreSQL conversation, run, review, and audit records | expose as `工作记录`; extract summaries only when useful and authorized |
| Semantic | evidence-backed project facts, risks, decisions, terminology | PostgreSQL `MemoryRecord` + `MemoryEvidenceLink` | proposed -> human approved -> active; source citations required |
| Procedural | reusable templates, writing rules, approval policies, team methods | published project/org knowledge and trusted Skills | owner/admin publishes; no autonomous org-wide writes |

Personal preference memory is a separate privacy scope implemented through the
optional Mem0 adapter. It is not a fifth business-memory category and cannot
authorize, override, or replace any PostgreSQL fact.

The current production evidence is intentionally recorded here: Mem0 is enabled
and the local sync ledger contains submitted capture records, while the project
memory ledger currently contains proposed records awaiting review. This is a
working integration, not a completed user-control experience.

### Research basis

- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
  separates thread-scoped checkpointers from cross-thread stores.
- [Mem0 memory types](https://docs.mem0.ai/core-concepts/memory-types) defines
  `user_id`, `agent_id`, `run_id`, and Platform-only `app_id` scopes.
- [Mem0 entity-scoped memory](https://docs.mem0.ai/platform/features/entity-scoped-memory)
  documents that user and assistant facts are attributed to separate entities;
  an AND filter across both entities returns nothing.
- [Claude Code memory](https://code.claude.com/docs/en/memory) demonstrates that
  users need explicit memory scope, inspection, and on/off controls.
- [Projects in ChatGPT](https://help.openai.com/en/articles/10169521-using-projects-in-chatgpt)
  treats project context, access control, and memory settings as separate product
  controls rather than one opaque assistant state.

### Control-plane acceptance bar

Memory is not complete until all of the following are true:

1. A user can see, disable, inspect, and delete personal preference memory.
2. A project member can review proposed semantic/project memories with citations.
3. A published procedural/team method has an owner, version, scope, and archive
   action.
4. Episodic history is visible as business work records, not raw runtime events.
5. Every memory recall is scope-filtered and traceable to the records used.
6. A Mem0 outage degrades personalization only; project work and evidence
   retrieval continue normally.

## Goal

Give BidPilot a durable, evidence-backed memory system that helps an agent
understand a user's working preferences and a team's bid knowledge across
sessions without treating chat history, model context, or LangGraph state as
business truth.

The product name for the shared project layer is **Bid Wiki**. It is not a
generic chat memory feature: it is a maintained, reviewable knowledge layer
for a bid workspace.

## Product contract

The system maintains four different things and must not blur them together:

| Layer | Purpose | Source of truth | Lifetime |
| --- | --- | --- | --- |
| Runtime state | Current tool loop, pending approval, graph checkpoints | LangGraph checkpointer plus RuntimeRun | One run/thread |
| Conversation record | What a user and assistant said | ChatConversation/ChatMessage | User-managed session history |
| Evidence retrieval | Raw document facts with locators | KnowledgeChunk and source documents | Project material lifecycle |
| Governed memory | Distilled preferences, decisions, procedures, risks, and linked concepts | PostgreSQL memory ledger | Versioned, scoped, reviewable |

The wiki is a **derived knowledge layer**. It may help select and summarize
context, but it never replaces source evidence in a generated bid response.
Every response that relies on a wiki record must retain its supporting source
locator or explicitly state that it is a human-authored preference or decision.

## Scope model

Every record belongs to exactly one scope:

- `user_private`: a personal style or workflow preference, readable only by
  its owner and organization administrators through audited break-glass access.
- `project_shared`: project facts, decisions, procedures, risks, and entities,
  readable through normal project capability checks.
- `org_shared`: reusable approved playbook knowledge. This is intentionally
  disabled for automatic writes in the first release; an owner must approve it.

No cross-org query is permitted. A record is filtered by organization and scope
before any lexical, vector, graph, or model operation. User-private records are
also filtered by owner before retrieval.

## Data model

The first implementation adds a relational memory ledger rather than a new
graph database:

### `memory_record`

- immutable identifier, org, optional project, optional owner user;
- scope, kind (`preference`, `fact`, `decision`, `procedure`, `risk`,
  `summary`, `entity_note`), status (`proposed`, `active`, `superseded`,
  `rejected`, `deleted`), and privacy classification;
- user-facing title and Markdown body plus a bounded structured JSON payload;
- deterministic `retrieval_text`, profile-aware embedding fields, and a
  content fingerprint;
- confidence as a routing signal, never as a claim of truth;
- version lineage (`supersedes_id`, `superseded_by_id`), expiry, and timestamps.

### `memory_evidence_link`

A system-produced memory record requires one or more links to a source
document chunk, requirement, evidence item, chat message, or audit event. The
link stores an evidence role (`supports`, `contradicts`, `derived_from`) and a
validated locator snapshot. Manual decisions may have no raw-document link but
must have a human actor and audit event.

For direct user writes, the API resolves every supplied source identifier in
the caller's authorized project scope before it creates the link. The server,
not the client, derives the citation label and locator snapshot. A client may
not claim another project, a nonexistent identifier, or another person's human
decision as provenance.

### `memory_entity` and `memory_relation`

These tables are a projection of approved records, not an independently
invented graph. An entity has a canonical name, type, aliases, and source
record. A relation has typed endpoints, predicate, status, and supporting
record/evidence. The later visual graph renders only active, authorized,
evidence-backed entities and relations.

### `memory_compilation_run`

This records a background compile/maintenance request, input source ids,
profile/config snapshot, result counts, safe failure category, and review
outcome. It makes the expensive distillation step measurable and retryable.

## Write policy

No model can silently create permanent memory. It can only return a typed
`MemoryProposal` with a bounded title, kind, scope, summary, evidence ids, and
expiry suggestion.

| Write source | Default behavior |
| --- | --- |
| Explicit user request such as "记住我的偏好" | Create a user-private proposal; user confirms the write. |
| Source-document ingestion | Create project-shared proposals; automatic activation is allowed only for deterministic metadata, never for policy/decision claims. |
| Assistant task outcome | Propose a project memory only when a tool result or evidence link supports it. |
| Human review/decision | Write an active decision record immediately and audit it. |
| Background maintenance | May supersede stale facts only after policy validation; contradictions create a proposal, never destructive overwrite. |

Deletion is a tombstone operation: the active record is no longer retrieved,
its vector is cleared, a deletion audit event is written, and lineage remains
available to authorized auditors. Checkpoint/context caches receive a memory
version token so deleted records cannot survive a later resume unnoticed.

## Read and context policy

The assistant and workflow never receive all memory. A `MemoryContextPack` is
built for a single authorized request:

1. resolve organization, user, project, capability, and privacy scope;
2. load a compact conversation/task summary when it exists;
3. retrieve bounded active memory records with the same embedding profile and
   lexical fallback rules as Retrieval 2.0;
4. retrieve raw evidence separately through the project evidence retriever;
5. remove superseded, expired, deleted, contradictory-unresolved, and
   unsupported records unless a user explicitly asks to inspect them;
6. attach provenance and a deterministic memory-version token.

The context pack has a token budget. It includes titles, concise body excerpts,
scope labels, and citations, not unrestricted chat logs or model reasoning.

## LangGraph integration

LangGraph remains the execution engine, not the memory database:

- `thread_id` is derived from a conversation or RuntimeRun and is required for
  every invocation;
- PostgreSQL-backed checkpoints support interruption, resume, and run history;
- a `load_memory_context` node obtains an authorized context pack before
  drafting or tool planning;
- a `propose_memory_updates` node emits structured proposals after a successful
  run; it cannot activate privileged project/org knowledge itself;
- existing human approval interrupt/resume controls are used for decisions,
  destructive changes, and memory activation where policy requires it.

LangGraph Store may later cache an approved projection for graph-local use, but
the PostgreSQL memory tables remain the business source of truth and audit
boundary.

## Bid Wiki UX

The project workspace gains a **Knowledge** area rather than a decorative global
graph tab. It has:

- an evidence-backed wiki page list and searchable memory ledger;
- proposed changes with approve, reject, edit, and expiry controls;
- a source panel that jumps to raw materials or human decisions;
- an entity/relation map that starts as a readable 2D evidence map;
- an optional 3D view only after the project has enough credible graph data.

The assistant may say "I will remember this" only after a memory proposal has
been accepted. It exposes which memories were used in an answer and lets users
open, correct, or delete them.

## Evaluation and release gates

MemoryBench scenarios must verify:

- private preference recall never crosses users, projects, or organizations;
- a project fact is not surfaced without supporting evidence or a human decision;
- superseding and deleting a record removes it from future context packs;
- stale or contradictory facts are shown as unresolved instead of silently
  overwritten;
- a user can inspect every record used in a response;
- no automatic writer creates an org-shared memory;
- a provider outage degrades to evidence retrieval without fabricating memory.

No 3D visualization or automatic background compiler ships as a production
claim until these gates pass on frozen fixtures and a human reviewer can trace
every displayed node back to a source.

## Non-goals for the first release

- a new Neo4j/graph-database service;
- unconstrained autonomous self-modification;
- permanent storage of hidden chain-of-thought;
- organization-wide automatic knowledge propagation;
- using semantic similarity as authorization or factual verification.

## Profile-memory provider decision (2026-08-22)

The reviewed implementation adds the official `mem0ai==2.0.18` Platform SDK as
an optional adapter for low-risk user-profile preferences. It does not replace
this document's PostgreSQL memory ledger. API recalls profile context before a
Pi turn; Worker captures a bounded successful exchange asynchronously; a local
`Mem0ProfileSync` row provides idempotency and account-deletion tracking.
Mem0 is scoped with `user_id`, `agent_id`, and organization `app_id`, and all
provider calls fail open. Tender facts, requirements, evidence, decisions and
graph proposals remain in the reviewed BidPilot tables. See
`docs/architecture/assistant-harness-runtime.md` for the runtime boundary.

## Sources

- LangGraph persistence and Stores:
  https://docs.langchain.com/oss/python/langgraph/persistence
  https://docs.langchain.com/oss/python/langgraph/stores
- LangChain long-term memory guide:
  https://docs.langchain.com/oss/python/langchain/long-term-memory
- Karpathy LLM Wiki idea:
  https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- Retrieval 2.0 design:
  `docs/superpowers/specs/2026-07-17-bidpilot-retrieval-2-design.md`
