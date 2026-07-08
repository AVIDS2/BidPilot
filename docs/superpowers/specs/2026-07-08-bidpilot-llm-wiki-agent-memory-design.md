# BidPilot LLM Wiki, Knowledge Graph, and Agent Memory Design

## Goal

Turn BidPilot from a collection of project pages and chat tools into an agent-first bid execution workspace with a durable knowledge layer.

The current product feels vague because the main product spine is incomplete:

- project data exists, but there is no explicit knowledge layer
- the assistant can operate tools, but it does not yet feel like it understands the user's organization over time
- workflow visualization exists, but it is not connected to a broader map of bid knowledge, evidence, requirements, and decisions
- the app navigation still exposes low-value pages as first-class sections while hiding the real work loop

This design introduces an LLM Wiki and knowledge graph layer that both humans and agents can inspect, edit, and use.

## Research Summary

### Karpathy-style LLM Wiki

Karpathy's LLM Wiki idea is best understood as a method, not as a component library:

- use LLMs to maintain a human-readable knowledge base
- keep knowledge inspectable instead of hiding everything inside vector search
- use generated pages, links, entities, citations, and summaries as a shared interface between humans and agents
- let the knowledge base improve over time as new source material and user feedback arrive

Reference: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

There is a community `llm_wiki` desktop implementation, but it should be treated as inspiration only. It is not a commercial SaaS-ready component library, and its GPLv3 license makes direct code copying risky for this repository unless the whole product licensing strategy changes.

Reference: https://github.com/nashsu/llm_wiki

### LangGraph Official Methodology

LangGraph fits this problem when it is kept in the execution layer:

- checkpointers preserve thread-local state and resumable execution
- Stores hold cross-thread, app-defined long-term memory
- `interrupt()` and `Command(resume=...)` support human approval
- orchestrator-worker patterns support parallel extraction, drafting, and synthesis
- agent loops support tool use with bounded iterations

References:

- https://docs.langchain.com/oss/python/langgraph/persistence
- https://docs.langchain.com/oss/python/langgraph/stores
- https://docs.langchain.com/oss/python/langgraph/interrupts
- https://docs.langchain.com/oss/python/langgraph/workflows-agents

BidPilot must preserve the existing architectural rule: PostgreSQL is the business source of truth. LangGraph state is execution state, not product truth.

## Product Thesis

BidPilot should become a bid execution operating system:

- `Projects` hold the concrete workspace.
- `Agent` is the primary command surface.
- `LLM Wiki` is the living knowledge layer.
- `Knowledge Graph` shows how requirements, evidence, documents, claims, people, vendors, and deliverables connect.
- `Workflow Agent` runs long bid-production workflows with visible state.
- `Reviews` and `Deliverables` turn generated work into accountable output.

The assistant should not merely answer from chat history. It should read and write through this knowledge layer with strict permissions and provenance.

## Recommended Architecture

### Approach A: Embed the Existing LLM Wiki Project

Rejected for v1.

Pros:

- fastest conceptual reference
- already demonstrates local knowledge graph behavior
- may use useful patterns such as generated wiki pages and graph layouts

Cons:

- not designed as a BidPilot SaaS module
- license risk for direct code reuse
- would create a second product inside BidPilot
- not aligned with current PostgreSQL, pgvector, MinIO, FastAPI, React architecture

### Approach B: Build BidPilot-Native LLM Wiki

Recommended.

Pros:

- keeps business truth in PostgreSQL
- reuses current project, bundle, parsed asset, knowledge chunk, evidence, workflow, and assistant systems
- can expose a polished first-party user experience
- can enforce organization isolation, audit, quota, approval, and deletion rules
- lets the assistant and workflow agent share the same knowledge substrate

Cons:

- requires schema and API design
- requires a staged migration from current knowledge chunks into wiki pages and graph entities
- requires careful UI design to avoid another "demo-looking" tab

### Approach C: Introduce a Dedicated Graph Database

Deferred.

Pros:

- strong graph traversal at large scale
- useful if customer deployments have millions of entities and edges

Cons:

- too much infrastructure for the current stage
- duplicates PostgreSQL truth
- increases ops burden on the VPS
- not necessary before proving the product loop

Decision: use Approach B now, with PostgreSQL relational graph tables and pgvector. Revisit Neo4j, Kuzu, or another graph database only after production usage proves that PostgreSQL traversal is insufficient.

## Information Architecture

The app navigation should be reorganized around real work, not miscellaneous pages.

### Proposed App Navigation

Primary sections:

- `Workbench`: operational dashboard and recommended next actions
- `Agent`: full-page agent workspace
- `Projects`: bid project list and project workspaces
- `Knowledge`: LLM Wiki, knowledge graph, evidence map, memory review
- `Workflows`: running and historical workflow executions
- `Reviews`: pending approvals, comments, quality gates
- `Deliverables`: exportable bid packages and final documents
- `Providers`: model providers, keys, model choices, quotas
- `Usage`: plan, limits, billing, audit summaries
- `Settings`: organization, team, security, email, integrations

Secondary/help pages:

- pricing
- docs
- guides
- changelog

These should not compete with the work loop inside the authenticated app. They can live in a help menu or public site.

### Knowledge Section

The `Knowledge` section contains:

- `Bid Wiki`: generated and editable wiki pages
- `Graph`: 2D/3D entity and evidence graph
- `Sources`: uploaded documents, parsed assets, chunks, extraction status
- `Evidence`: requirement-to-evidence traceability
- `Memory`: user/org/project memories and approval history
- `Contradictions`: detected conflicts and stale knowledge

## Data Model

### Source Layer

Existing objects remain the ingestion roots:

- `Project`
- `Bundle`
- `SourceDocument`
- `ParsedAsset`
- `KnowledgeChunk`
- `RequirementItem`
- `Evidence`
- `ExecutionRun`
- `Deliverable`
- `DeliverableSection`

### Wiki Layer

Add first-class wiki records:

- `WikiSpace`
- `WikiPage`
- `WikiPageVersion`
- `WikiPageSource`
- `WikiClaim`
- `WikiClaimEvidence`

`WikiSpace` scopes knowledge:

- `global`: system templates and scenario knowledge
- `org`: organization playbooks and preferences
- `project`: project-specific facts
- `user`: personal preferences and working style

`WikiPage` examples:

- `项目概览`
- `招标人画像`
- `评分办法`
- `技术响应策略`
- `商务响应策略`
- `竞品/供应商线索`
- `历史投标复盘`
- `常用措辞和禁用词`

Every generated statement that may affect bid output should either have evidence or be marked as an inference.

### Graph Layer

Add relational graph tables:

- `KnowledgeEntity`
- `KnowledgeRelation`
- `KnowledgeEntityMention`
- `KnowledgeGraphSnapshot`

Entity types:

- `project`
- `document`
- `requirement`
- `evidence`
- `claim`
- `section`
- `deliverable`
- `organization`
- `person`
- `vendor`
- `product`
- `technology`
- `deadline`
- `risk`
- `decision`
- `memory`

Relation types:

- `requires`
- `evidenced_by`
- `mentions`
- `depends_on`
- `conflicts_with`
- `supports`
- `drafted_into`
- `reviewed_by`
- `belongs_to`
- `similar_to`
- `learned_from`

Graph records must include:

- tenant scope
- project scope when applicable
- source ids
- confidence
- created_by: system, agent, user, workflow
- last_verified_at

### Memory Layer

Add memory records:

- `AgentMemory`
- `AgentMemoryCandidate`
- `AgentMemoryAudit`

Memory scopes:

- `user`: personal preferences
- `org`: organization style and reusable facts
- `project`: project-local decisions
- `session`: temporary context that should not persist

Memory categories:

- `preference`
- `writing_style`
- `business_fact`
- `workflow_pattern`
- `provider_preference`
- `review_rule`
- `risk_note`
- `do_not_store`

Low-risk preferences can be auto-saved. Business facts, organization-wide rules, and anything derived from uploaded documents should become a candidate first and require user confirmation or admin approval.

Secrets, provider keys, passwords, private tokens, personal identity documents, and unrelated private user content must not be stored as agent memory.

## LangGraph Design

### Graph 1: Assistant Operator Graph

Purpose: let the assistant operate BidPilot safely.

Core nodes:

- `load_context`
- `retrieve_wiki_context`
- `retrieve_graph_context`
- `plan_actions`
- `execute_tool`
- `request_approval`
- `summarize_result`
- `propose_memory`

State contains:

- `conversation_id`
- `user_id`
- `org_id`
- `current_project_id`
- `approval_mode`
- `provider_config_id`
- `reasoning_effort`
- `tool_results`
- `wiki_context`
- `memory_candidates`

Persistence:

- production uses Postgres-backed checkpointer
- `thread_id` maps to conversation id
- long-term memory is stored in product tables and optionally mirrored through LangGraph Store access

### Graph 2: Wiki Compiler Graph

Purpose: convert source material into wiki pages and graph entities.

Core nodes:

- `select_sources`
- `extract_entities`
- `extract_claims`
- `link_evidence`
- `detect_conflicts`
- `draft_wiki_pages`
- `review_wiki_update`
- `persist_wiki_snapshot`

Pattern:

- orchestrator-worker for document chunks and entity extraction
- reducers merge entities, claims, and source links
- human approval for high-impact org-wide wiki updates

### Graph 3: Workflow Agent Graph

Purpose: run bid generation work.

Existing nodes remain useful:

- `rfp_parser`
- `knowledge_retriever`
- `section_drafter`
- `quality_reviewer`
- `human_approval`
- `persist_result`

Required change:

- `knowledge_retriever` should query the LLM Wiki and graph context in addition to raw chunks
- drafting prompts should cite wiki claims and evidence links
- successful runs should feed back into the wiki as project-local pages and memory candidates

## Agent Context Assembly

Every assistant turn should build a context pack:

1. Current user and organization profile.
2. Current page and selected project.
3. Active sandbox and approval mode.
4. Recent conversation summary.
5. Relevant Wiki pages.
6. Graph neighbors around current project, requirements, documents, and memories.
7. Current workflow runs and pending approvals.
8. Provider and quota status.

The model sees a compact context pack, not raw database dumps.

## Write-Back Policy

The agent may propose knowledge updates after actions.

Auto-write:

- UI preference
- language preference
- formatting preference
- repeated workflow preference

Needs confirmation:

- organization-wide writing style
- reusable bid strategy
- project requirement interpretation
- inferred customer preference
- contradiction resolution
- anything that changes future generated content materially

Forbidden:

- decrypted API keys
- passwords
- payment credentials
- private tokens
- hidden chain-of-thought
- personal data unrelated to bid work

All writes need provenance and audit.

## Frontend Visualization

### Component Strategy

Do not directly copy the community LLM Wiki frontend.

Use mature graph visualization libraries through a BidPilot-owned wrapper:

- `Graphology`: graph data model and layout utilities
- `Sigma.js`: stable 2D WebGL graph view
- `react-force-graph-3d`: optional 3D force-directed graph explorer
- `Reagraph`: evaluate as an alternative React-first graph renderer
- `React Flow`: continue using for workflow DAG visualization, not general knowledge graph exploration

Reference links:

- https://www.sigmajs.org/
- https://graphology.github.io/
- https://github.com/vasturiano/react-force-graph
- https://reagraph.dev/
- https://reactflow.dev/

### UX Modes

Default mode: `Evidence Map`

- 2D graph
- fast and readable
- good for business users
- shows requirement, evidence, document, claim, and section links

Immersive mode: `3D Knowledge Space`

- optional toggle
- useful for demo, exploration, and high-level discovery
- nodes breathe based on status and confidence
- current workflow node can pulse when a graph is being generated
- disabled or simplified on low-end/mobile devices

Workflow mode: `Execution Graph`

- React Flow DAG
- shows actual workflow agent nodes
- status breathing lights
- stream-driven updates
- no 3D here because workflow status should be precise and readable

### Visual Language

Use a cooler blue-violet glow for intelligence and exploration.

Avoid making the whole product neon green. Keep the lime accent only for primary completion or "go" actions.

Suggested mapping:

- blue/violet: agent intelligence, graph, active reasoning
- cyan: evidence and source links
- lime: confirmed success and primary CTA
- amber: needs review
- red: destructive or blocked
- gray: unknown or inactive

## API Surface

### Wiki APIs

- `GET /knowledge/wiki/spaces`
- `GET /knowledge/wiki/pages`
- `GET /knowledge/wiki/pages/{id}`
- `POST /knowledge/wiki/pages/{id}/accept-version`
- `POST /knowledge/wiki/rebuild`

### Graph APIs

- `GET /knowledge/graph`
- `GET /knowledge/graph/entity/{id}`
- `GET /knowledge/graph/neighborhood`
- `POST /knowledge/graph/rebuild`

### Memory APIs

- `GET /agent/memories`
- `GET /agent/memory-candidates`
- `POST /agent/memory-candidates/{id}/approve`
- `POST /agent/memory-candidates/{id}/reject`
- `DELETE /agent/memories/{id}`

### Assistant APIs

Extend `POST /assistant/stream` to return events:

- `assistant.context_loaded`
- `assistant.wiki_search_started`
- `assistant.wiki_search_completed`
- `assistant.graph_search_completed`
- `assistant.memory_candidate_created`
- `assistant.memory_write_completed`

Raw wiki or graph payloads should not be dumped into chat. The UI renders concise user-facing summaries.

## Permissions and Sandboxing

The sandbox has to cover memory and wiki writes.

Read-only:

- search wiki
- search graph
- list memories
- inspect source links

Low-risk write:

- save user preference
- create session-local memory
- draft project-local wiki page version

Approval required:

- promote project wiki knowledge to org wiki
- save reusable organization memory
- resolve contradiction
- delete memory
- rebuild graph for a large project if it consumes provider credits

Forbidden unless admin:

- edit provider keys
- purge organization wiki
- change billing policy
- export all organization knowledge

## Migration from Current Product

### Current Assets to Reuse

- `KnowledgeChunk`
- `RequirementItem`
- `Evidence`
- `ParsedAsset`
- `ExecutionRun`
- `Assistant Action Audit`
- `WorkflowCanvas`
- `AgentProgress`
- `AIAssistantPanel`

### Missing Pieces

- wiki page and version model
- graph entity and relation model
- memory candidate approval model
- wiki rebuild worker task
- graph visualization route
- agent context pack service
- user-facing knowledge write UI

## Implementation Phases

### Phase 0: Product Spine Cleanup

Purpose: reduce cloudiness before adding more features.

Scope:

- reorganize authenticated navigation
- remove decorative active-tab brackets
- move docs/pricing/help out of primary app work loop
- add `Agent`, `Knowledge`, `Workflows`, `Reviews`, and `Deliverables` as real product surfaces

No schema change.

### Phase 1: Wiki and Memory Schema

Scope:

- create wiki, graph, and memory tables
- add migrations
- add CRUD and query services
- add tenant isolation and audit fields

### Phase 2: Wiki Compiler MVP

Scope:

- build source-to-wiki compiler for one project
- generate project overview, requirements, evidence map, and drafting strategy pages
- generate graph entities and relations
- add conflict detection stubs

### Phase 3: Knowledge UI

Scope:

- add Knowledge section
- add Wiki pages
- add Evidence Map with Sigma.js
- add optional 3D Knowledge Space with react-force-graph-3d behind a feature flag
- add Memory review screen

### Phase 4: Agent Integration

Scope:

- add context pack service
- assistant retrieves wiki and graph context before answering
- assistant creates memory candidates after meaningful work
- assistant can open wiki pages, graph neighborhoods, and evidence paths
- assistant can explain why it used a piece of knowledge

### Phase 5: Workflow Integration

Scope:

- workflow `knowledge_retriever` reads from wiki and graph
- successful workflow outputs update project wiki candidates
- workflow graph UI links execution nodes to source wiki/evidence nodes

### Phase 6: Production Hardening

Scope:

- memory/wikis audit exports
- data retention rules
- org-level memory policies
- eval tests for context quality
- graph rebuild queue and rate limits
- provider-cost quota enforcement for wiki rebuilds

## Success Criteria

The design succeeds when:

- a new user can understand the platform from the navigation alone
- uploaded documents produce inspectable Wiki pages and graph nodes
- the assistant can answer using the Wiki and show its source trail
- the assistant can remember user/org preferences with approval
- workflow agent drafting uses evidence and wiki claims instead of raw chunks only
- graph visualization helps users understand requirements, evidence, and outputs
- risky memory/wiki writes are auditable and reversible
- no raw secrets, tool JSON, or hidden chain-of-thought leaks into the UI

## Non-Goals

- copying GPL project code into BidPilot
- replacing PostgreSQL with a graph database in v1
- making 3D graph the only visualization mode
- storing all chat transcripts as long-term memory
- autonomous background knowledge mutation without user-visible audit
- arbitrary web browsing or filesystem access by the product agent

## Open Decisions for Implementation Planning

These are implementation-level decisions, not product blockers:

- choose Sigma.js first or Reagraph first for the 2D graph wrapper
- decide whether `react-force-graph-3d` ships in the initial Knowledge section or behind a later feature flag
- decide graph node count thresholds for mobile fallback
- decide whether wiki rebuild uses the existing worker queue or a separate task type
- decide exact migration naming after inspecting current migration history

