# Agent Engineering Glossary

This is a living glossary. Each entry should eventually link to a BidPilot implementation, test, trace, or evaluation.

| Term | Plain-language meaning | BidPilot meaning |
| --- | --- | --- |
| Workflow | A mostly known sequence of steps | Parse tender -> retrieve evidence -> draft -> review -> persist |
| Agent | A model-driven loop that chooses its next action | Assistant decides which platform tool or workflow to invoke |
| Router | A one-time classifier that selects one bounded path | `classify_locally` or the structured model router chooses one BidPilot capability or asks for missing input |
| Harness | The runtime wrapper around the model, tools, state, and policies | Tool registry, context pack, approval policy, event stream, and loop limits |
| ReAct | Reasoning/action/observation loop | Select tool, execute it, inspect result, continue or finish |
| Tool calling | Model emits a typed request for an external capability | Search projects, import files, start drafting, export deliverables |
| Orchestrator-worker | One planner fans work out to specialized workers and merges results | Split document extraction or section drafting across workers |
| HITL | Human-in-the-loop approval or correction | Approve destructive actions and high-impact generated content |
| Checkpointer | Durable snapshots of one execution thread | Resume a conversation or workflow after interruption |
| Runtime control plane | Product-owned lifecycle, policy, audit, and event layer around an Agent | `RuntimeRun`, `RuntimeEvent`, `RuntimeAction`, and `RuntimeApproval` in PostgreSQL |
| Event replay cursor | Highest durable event sequence a client has processed | Reconnect with `after_sequence` without repeating a capability call |
| Idempotency key | Stable identifier that makes a repeated request safe | `(run_id, action_key)` prevents a resumed graph node from mutating twice |
| Compatibility adapter | Temporary translation layer during a migration | Runtime events render as legacy `assistant.*` SSE until the UI consumes the typed feed directly |
| Store | Cross-thread application memory | User/org/project preferences and validated facts |
| Working memory | Context needed for the current turn | Current project, plan, tools, pending approval, recent messages |
| Episodic memory | What happened in previous tasks | Run outcomes, review decisions, failed attempts, corrections |
| Semantic memory | Stable facts and concepts | Tender requirements, company capabilities, customer facts |
| Procedural memory | Reusable ways of doing work | Organization playbooks, writing rules, approval policies |
| Provenance graph | A graph whose edges point back to evidence | The current Evidence Map shows `memory -> cites -> source`; it does not prove the claim |
| Entity | A canonical named thing in a controlled domain vocabulary | A project-local requirement, deliverable, bidder, deadline, or standard |
| Relation | A typed connection between two entities | `requirement requires deliverable`, backed by a reviewed source link |
| Entity resolution | Deciding whether two mentions refer to the same thing | Normalizing a project-local entity key; aliases help presentation but do not grant access |
| Graph proposal | A typed suggested set of entities and relations, before approval | `MemoryGraphProposal` is source-bound and enters the existing memory review path |
| Graph materialization | Turning an approved proposal into durable graph rows | Deferred until the reviewed persistence schema and lifecycle rules are implemented |
| GraphRAG | Retrieval that uses graph structure as an additional index | Not enabled as authoritative BidPilot context; it needs a measured user-decision benefit first |
| Graph precision / recall | Respectively, how many graph items are correct and how many expected items were found | MemoryGraphBench measures entities and relations separately, plus evidence and scope safety |
| Dense retrieval | Search by embedding similarity | Find semantically related evidence chunks |
| Sparse retrieval | Search by exact terms or lexical matching | Match acronyms, legal phrases, model numbers, and names |
| Hybrid retrieval | Fuse dense and sparse search | Combine pgvector and PostgreSQL full-text results |
| RRF | Rank fusion that combines result lists | Merge dense and sparse candidates before reranking |
| Reranker | A second model that scores query-document pairs | Improve evidence precision after broad recall |
| Context compression | Reduce retrieved material to useful facts | Keep the prompt small while preserving citations |
| Grounding | Tie a generated claim to a source | Every important bid claim links to source document/page/chunk |
| Trace | End-to-end record of an agent invocation | User request -> model -> tool -> workflow -> output |
| Span | One timed operation inside a trace | Retrieval, rerank, model call, tool call, or DB write |
| Eval | A repeatable quality measurement | Retrieval recall, tool accuracy, citation faithfulness, task success |
| AssistantBench | Offline evaluation of structured Agent routing and policy safety | Scores intent mode, tool route, missing scope, approval parity, typed confirmation, and unknown capabilities without calling a model |
| Control fixture | A deterministic example used to prove the evaluator itself | `assistant-control.json` may score 100% but is rejected as a real quality baseline |
| Structured pending-input state | Small durable state for one incomplete task, distinct from chat history | Stores only capability, redacted arguments, and missing fields for 30 minutes so the next Operator turn knows what remains |
| Evaluation capture manifest | Private mapping from a benchmark case to an approved runtime trace | Offline AssistantBench capture reads durable plan/action/approval facts but emits no messages, ids, argument values, or model payloads |
| SLO | Reliability target for a service | P95 assistant latency, workflow completion, approval safety |

## Project Access: Concepts Applied in BidPilot

### RBAC, capabilities, and ABAC

**RBAC** maps a person to a role. BidPilot uses the project roles `owner`, `manager`, `contributor`, `reviewer`, and `viewer` through the durable `ProjectMember` relation. Roles are convenient for people to understand, but routes and Agent tools do not ask only "is this user a reviewer?". They ask whether the role grants one named **capability**, such as `requirements.review` or `workflow.run`.

That is a small capability-based policy layer built on top of RBAC. It makes a product change auditable: adding a new tool means declaring exactly which capability it needs instead of copying role checks into many endpoints. **ABAC** (attribute-based access control) is the broader pattern of deciding from attributes such as tenant, project, status, time, or classification. BidPilot already uses ABAC-style attributes for organization, project membership, disabled-account state, and soft-delete state; a future data-classification policy can extend the same resolver.

### IDOR prevention

An **IDOR** (insecure direct object reference) occurs when someone can change a URL or API id and access another customer's object. A UUID does not solve this. BidPilot resolves each project-scoped id back to its project and then calls `require_project_capability`. A user outside that project receives `404`, so the API does not confirm that the object exists; a known member without the required capability receives `403`.

The implementation path is deliberately visible: `ProjectMember` -> `resolve_project_access` -> `require_project_capability` -> route or Agent tool. The test suite exercises both conventional APIs and assistant tools because an Agent must not become an alternate path around the product's permission model.

### Authorization is not approval

**Authorization** answers whether an actor is allowed to perform an action at all. **Approval** answers whether an allowed action needs a human decision now. A confirmation dialog can never grant `project.delete` to a viewer. BidPilot evaluates capability first, then applies the approval mode to the exact action arguments. This ordering is the difference between a safe human-in-the-loop design and a permission-escalation bug.

### Why RLS remains a second layer

PostgreSQL **row-level security (RLS)** can independently filter rows inside the database. It is valuable defense in depth, especially if a future query forgets the application resolver. It is not enabled yet because it requires database-session tenant context, worker and migration compatibility, and a full regression pass across relational queries, pgvector, exports, and background jobs. Until then, the access resolver is the enforced boundary and must be covered by cross-role tests.

## Unified Runtime: Concepts Applied in BidPilot

### Checkpoint versus product truth

A LangGraph **checkpoint** is an execution snapshot. It lets a graph restart after a worker crash or an `interrupt()`, but it is not a safe user-facing audit record: its shape is framework-specific, it may contain internal state, and it cannot by itself prove that a business write happened exactly once.

BidPilot separates that concern. `RuntimeEvent` is the redacted, append-only public timeline; `RuntimeAction` is the idempotent business-effect boundary; `RuntimeApproval` records the human decision. The graph checkpoint only remembers how to resume the graph. This distinction is why the product can replay a timeline without exposing prompts, chain-of-thought, or raw provider/tool data.

### Why sequence cursors matter

Streaming connections fail routinely through browsers, mobile networks, reverse proxies, and deployment restarts. A client must not solve that by replaying the original user request: a request may have already created a project, submitted a draft job, or started an export. Instead, it remembers the largest event sequence it rendered and asks for later events only. The action idempotency key protects the server side; the event cursor protects the UI side.

### Approval is a graph resume boundary

When a LangGraph operator pauses for approval, resolving a database row is not sufficient. The paused graph also needs `Command(resume=...)` with the original `thread_id`, otherwise it can remain suspended or repeat planning incorrectly. BidPilot therefore refuses a generic REST resolution that would bypass this boundary. The Assistant confirmation path resumes the graph, and a future independent approval inbox must call an equally safe resume service.

### Safe cancellation boundary

A cancellation request is not a hard process kill. Hard-killing a Worker can leave a partial database write, an unknown provider call outcome, or a corrupted checkpoint. BidPilot records `cancel_requested` first. The Worker checks that durable state before and after each LangGraph node; it lets the currently executing node reach its own transaction boundary, refuses to start another node, then writes the terminal `cancelled` state and public event. This is called **cooperative cancellation** or **safe-boundary cancellation**.

### Retry lineage

A retry should usually create a new child run that references the failed or cancelled parent. Reusing one `ExecutionRun` destroys the answer to basic audit questions: which attempt produced this result, which provider cost belongs to which attempt, and what did the user approve? BidPilot now creates child `ExecutionRun` and `RuntimeRun` records, preserves both parent links, reruns project capability and quota checks, and emits fresh usage and audit evidence. A unique `(parent_execution_run_id, attempt_number)` constraint plus a parent-row lock keeps the history linear under concurrent requests: retry from the latest failed child, never create a sibling fork. Only a runtime-linked workflow can retry, because a legacy run does not contain a trustworthy policy/provider snapshot. A retry may reuse BYOK only when the requester owns the original provider configuration; otherwise it is denied rather than silently consuming a different key or the platform budget.
