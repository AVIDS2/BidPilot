# BidPilot Product and Agent Re-foundation v2

## Status

- Date: 2026-07-14
- Status: Approved direction, implementation baseline
- Supersedes: feature-by-feature MVP expansion as the primary product strategy
- Preserves: PostgreSQL business truth, provider adapters, LangGraph execution boundaries, existing project/document/review/export foundations, and a scenario-neutral internal control plane with explicit BidPilot extensions

## Executive Decision

BidPilot is an **AI bid compliance and response execution platform** for teams producing complex technical bids.

It is not positioned as:

- a generic document chat product;
- a long-form writing wrapper;
- a construction tender marketplace;
- a CA, pricing, or cost-estimation suite;
- a decorative multi-agent demo.

The product promise is:

> 让漏项在提交前暴露，而不是在评标后发现。

The commercial wedge is the period between receiving a tender package and establishing a trustworthy response plan. BidPilot turns tender sources, supplier evidence, team responsibilities, generated claims, reviews, and final deliverables into one governed execution system.

## Competitive Standard

Overlap with competitors is not permission to be weaker.

BidPilot uses a three-level standard:

### 1. Table Stakes: Reach or Exceed Market Quality

Capabilities users already expect must be complete, reliable, and pleasant:

- PDF, DOCX, image, and spreadsheet ingestion;
- structured requirement extraction;
- source locators and document previews;
- project and team workspaces;
- drafting, redrafting, review, versioning, and export;
- model provider configuration and platform-funded trial usage;
- conversation history, attachments, markdown, citations, and streaming tool status;
- responsive desktop and mobile layouts;
- stable authentication, email, quota, and account flows.

These are not differentiators, but weak execution here invalidates every claimed differentiator.

### 2. Differentiators: Win Decisively

BidPilot must lead in:

- requirement completeness and mandatory-item detection;
- requirement-to-evidence-to-claim-to-deliverable traceability;
- multi-role ownership, review, escalation, and closure;
- governed agent execution with clear approval boundaries;
- reusable organization knowledge without silent memory pollution;
- measurable quality, cost, latency, and recovery behavior;
- explainable output that can survive internal audit and customer review.

### 3. Deliberate Non-Competition

BidPilot will not currently chase:

- tender information marketplaces;
- construction costing and bill-of-quantities tooling;
- CA certificate ecosystems;
- procurement-side evaluation portals;
- a general-purpose workflow builder;
- arbitrary local computer or internet control.

If a buyer primarily needs those capabilities, another product may be the better choice. This honesty protects the product focus.

## Ideal Customer Profile

Initial ICP:

- software, cloud, cybersecurity, system integration, digital-service, and technical consulting companies;
- approximately 30 to 500 employees;
- 3 to 20 people participating in bid, presales, solution, legal, delivery, or review work;
- roughly 20 to 100 bid responses per year;
- tender packages commonly exceed 100 pages and involve at least three roles;
- response windows commonly range from 7 to 21 days;
- loss risk comes from omissions, weak evidence, inconsistent claims, and late collaboration rather than a lack of prose generation.

The first user is usually a bid manager or presales lead. The economic buyer is a sales, presales, delivery, or operations leader who cares about win readiness, labor cost, compliance risk, and organizational reuse.

## Core Product Artifact

The first valuable artifact is a **Bid Readiness Pack**, produced from tender documents and supplier materials.

It contains:

- executive project summary;
- deadlines, submission rules, qualification conditions, and mandatory clauses;
- scoring criteria and weighted opportunities;
- Requirement Ledger with exact source locators;
- initial coverage state for each requirement;
- evidence gaps and contradiction warnings;
- preliminary owner and reviewer assignments;
- response workload and risk overview;
- exportable Excel and Word views.

The user should obtain this artifact before asking the system to draft long sections.

## Product Spine: Requirement Ledger

The Requirement Ledger is the canonical operational view of a bid.

Each requirement should support:

- normalized text and original source text;
- requirement type: mandatory, scored, qualification, commercial, technical, delivery, formatting, submission;
- source document, page, section, table, and bounding locator when available;
- priority, score weight, deadline, and risk;
- coverage state: uncovered, partial, covered, disputed, not applicable;
- evidence readiness: missing, weak, sufficient, conflicting, expired;
- owner, reviewer, due date, and escalation state;
- linked evidence, claims, sections, deliverables, comments, approvals, and execution runs;
- extraction confidence and human verification state;
- full audit history.

The central trace is:

`Requirement -> Evidence -> Claim -> Deliverable`

Drafting is downstream of this trace, not the product center.

The customer-facing product is BidPilot. Internally, generic provenance, assignment, evidence, claim, review, execution, and audit concepts remain reusable. Bid-only concepts such as scoring weight, mandatory submission rules, and readiness policy live in explicit BidPilot extension records as defined by ADR 0003.

## Golden User Flow

1. A user creates a bid workspace or asks the Agent to create one.
2. The user uploads the tender package and available supplier evidence.
3. BidPilot parses sources and creates a Bid Readiness Pack.
4. The team verifies the Requirement Ledger and assigns owners.
5. BidPilot retrieves evidence and flags missing or conflicting support.
6. The Agent proposes an execution plan and requests approval for risky or costly actions.
7. Workflow agents draft sections against verified requirements and evidence.
8. Reviewers resolve gaps, comments, and quality gates.
9. BidPilot exports the final deliverable and an audit/coverage report.
10. Approved reusable knowledge becomes organization knowledge through governed write-back.

This flow must work through both conventional UI and the Agent command surface.

## Product Surfaces

### Workbench

Shows the current portfolio, deadlines, readiness, blockers, pending approvals, active runs, usage, and recommended next actions. It must be useful even when the account has no projects by offering a guided first run and sample dataset.

### Agent

A full-page operator workspace plus an optional side panel. It can navigate and operate the platform, but it does not replace inspectable business views.

The Agent must provide:

- multi-turn context;
- file and image attachment understanding;
- live tool and workflow progress in chronological order;
- user-facing tool names and summaries;
- configurable approval modes;
- model and reasoning controls where supported;
- resumable tasks and conversation history;
- source-backed answers and clear uncertainty;
- safe cancellation, retry, and recovery.

### Projects

Holds bid workspaces and project-level dashboards.

### Requirements

Provides the Requirement Ledger, coverage filters, ownership, bulk operations, risk views, and source inspection.

### Knowledge

Provides sources, reusable evidence, Bid Wiki pages, contradiction review, memory candidates, and evidence maps. The LLM Wiki supports the Requirement Ledger; it does not replace it.

### Workflows

Shows active and historical execution graphs, node status, retries, costs, traces, and outputs. React Flow visualizes execution DAGs. Status is streamed from backend events rather than simulated by the UI.

### Reviews

Centralizes pending approvals, requirement disputes, draft comments, quality failures, and knowledge write-back decisions.

### Deliverables

Manages output packages, versions, templates, export readiness, and final Word/PDF artifacts.

### Administration

Providers, usage, billing, organization, teams, permissions, security, audit, and integrations are secondary administration surfaces rather than the main work loop.

## Agent Architecture

### Control Plane

PostgreSQL remains the source of truth for:

- users, organizations, teams, and permissions;
- projects, requirements, evidence, claims, sections, and deliverables;
- policies, approvals, usage, audit, and billing;
- memories, wiki pages, graph entities, and provenance;
- execution run metadata and durable outcomes.

Redis stores transient queue and coordination state. MinIO/S3 stores source and generated artifacts. LangGraph checkpointers store resumable execution state but never replace product records.

### Unified Runtime Contract

Assistant operations, extraction jobs, and workflow agents must share a runtime contract containing:

- actor and tenant context;
- task and conversation identifiers;
- capability and tool metadata;
- policy decision and approval state;
- provider/model/reasoning configuration;
- usage reservation and settlement;
- event stream and trace identifiers;
- idempotency and recovery keys;
- structured result and failure envelopes.

Changing the orchestration engine must not change the business contract. A fake engine should pass the same contract tests as the LangGraph adapter.

### Capability Registry

Every Agent capability is registered with:

- stable capability id;
- user-facing localized name and description;
- input and output schema;
- read/write/destructive/cost/network classifications;
- required project and organization permissions;
- approval policy;
- idempotency behavior;
- audit and usage event definitions;
- UI renderer metadata.

Tool names and raw provider payloads must never be dumped into the user interface.

### Policy and Human Approval

Approval modes:

- `request`: approve all external, write, costly, or destructive actions;
- `risk_only`: auto-run reads and low-risk writes, approve risky actions;
- `full_access`: auto-run permitted actions, while irreversible deletion and organization-wide changes remain confirmed.

Approval decisions are durable, scoped to exact arguments, expire, and cannot be replayed for a different action.

### Runtime Graphs

The initial runtime has three bounded graph families:

1. Assistant Operator: understand, plan, retrieve, call capabilities, request approval, summarize, propose memory.
2. Bid Readiness Compiler: parse, extract, normalize, deduplicate, classify, locate, verify, and persist requirements.
3. Response Workflow: retrieve evidence, plan sections, draft, validate, review, revise, approve, and export.

Supervisor, router, orchestrator-worker, and subagent patterns are selected per task. More agents are not automatically better.

## Retrieval, Evidence, and Claims

The retrieval system must progress from vector-or-lexical fallback to a measured pipeline:

1. source and scope filtering;
2. lexical/BM25-style retrieval;
3. dense vector retrieval;
4. reciprocal-rank fusion;
5. cross-encoder or LLM reranking where cost permits;
6. citation and locator validation;
7. evidence sufficiency and contradiction checks.

Generated claims that materially affect a response must be:

- linked to evidence;
- explicitly marked as inference;
- or marked as unsupported and blocked from final approval.

## Knowledge and Memory

Memory is governed product data, not an automatic transcript dump.

Scopes:

- session: temporary execution context;
- user: personal preferences;
- project: decisions and interpretations for one bid;
- organization: approved reusable facts, style, evidence, and playbooks.

Memory categories include semantic facts, episodic outcomes, and procedural preferences. Every durable memory has provenance, confidence, owner, review state, retention policy, and deletion controls.

The LLM Wiki is a human-readable projection of approved knowledge. The graph connects requirements, evidence, claims, documents, people, decisions, and deliverables. A 2D evidence map is the default business view; 3D visualization remains optional and never substitutes for task completion.

## Evaluation: BidBench

BidPilot must prove value against strong general-purpose AI, not only against its previous version.

BidBench contains versioned, anonymized, public, or synthetic bid packages with human-reviewed ground truth for:

- mandatory requirements;
- scoring criteria;
- deadlines and submission constraints;
- qualification conditions;
- source locators;
- evidence matches;
- contradiction cases;
- expected coverage states;
- approval and recovery scenarios.

Baselines:

- carefully prompted general-purpose model with uploaded files;
- dense-only retrieval;
- lexical-only retrieval;
- current production pipeline;
- new hybrid and reranked pipeline.

Dataset tiers:

- development set: visible fixtures used while implementing metrics and extraction;
- frozen regression set: diverse packages whose labels and expected outputs change only through review;
- hidden acceptance set: private or separately controlled packages used to detect benchmark overfitting.

Mandatory and scored requirements in frozen and hidden sets require two-person review. Reports state sample count, document/layout mix, matching rules, micro and macro averages, prompt/model/provider versions, run count, and variance. Live baseline outputs are frozen as artifacts so a provider change cannot silently rewrite history.

Primary metrics:

- mandatory requirement recall;
- scoring-criterion recall;
- source-locator accuracy;
- evidence precision and recall;
- unsupported-claim rate;
- requirement closure completeness;
- task success rate;
- approval-policy correctness;
- recovery idempotency;
- latency and provider cost.

Provisional graduation targets, activated only after the frozen regression set covers at least 12 representative packages across at least four source/layout classes and the hidden acceptance set contains at least five independently reviewed packages:

- at least 95% recall on mandatory requirements in the golden set;
- at least 90% recall on scoring criteria;
- at least 98% correct source association for accepted requirements;
- zero accepted final claims without evidence or explicit inference status;
- zero cross-tenant retrieval in security tests;
- no duplicate durable outcome after worker interruption and resume;
- at least 15 percentage-point improvement over the frozen general-AI baseline on the combined completeness and traceability score.

Before that dataset bar is reached, reports are development baselines and must not be used as commercial quality claims. Targets may be revised only through a documented benchmark review, not to make a failing build pass.

## Enterprise Engineering Bar

### Security

- strict tenant and project authorization on every repository path;
- encrypted provider credentials with no frontend exposure;
- prompt-injection and malicious-document tests;
- approval replay protection;
- rate limits and abuse controls backed by durable/shared storage;
- retention, deletion, and export policies;
- secrets managed through environment or secret manager, never Git.

Until tenant isolation is proven across relational queries, vector retrieval, object storage, background jobs, exports, caches, audit, and admin paths, the product may claim only controlled pilot isolation rather than production multi-tenant certification.

### Reliability

- idempotent jobs and tool calls;
- durable retries with bounded backoff;
- worker crash and provider outage recovery;
- database migration and rollback procedures;
- backup and restore drills;
- clear degraded modes instead of silent stubs in production.

### Observability

- correlated request, task, run, model, tool, approval, and user-action traces;
- structured events and OpenTelemetry-compatible spans;
- model latency, token, cost, retrieval, and quality metrics;
- user-facing failure explanations without raw stack or provider payload leaks;
- operational dashboards and alert thresholds.

### Cost Governance

- server-side usage reservation before costly actions;
- settlement using actual tokens/units after completion;
- per-user, project, organization, and plan limits;
- platform-funded trial credits separated from BYOK usage;
- hard enforcement in backend policy, not UI-only warnings.

## Commercial Shape

### Free Entry

The acquisition experience is a limited Bid Health Check:

- upload a small tender package;
- receive a summary, several high-risk requirements, and a partial readiness score;
- no unlimited drafting or unrestricted official-provider usage.

### Paid Value

Paid plans unlock:

- full Requirement Ledger;
- organization evidence and knowledge reuse;
- team ownership and review workflows;
- governed Agent execution;
- complete drafting and export;
- audit, usage, and compliance reporting;
- higher quotas and enterprise identity/integration options.

BYOK reduces platform model cost but does not bypass security, rate, or policy controls.

## Final Deliverables

The goal is complete only when the repository and deployed candidate contain all of the following:

1. Product specification and ADRs that describe the final architecture and explicit non-goals.
2. BidBench datasets, baseline runners, reports, and CI quality gates.
3. Requirement Ledger schema, API, UI, collaboration, audit, and exports.
4. Unified runtime contract, capability registry, policy engine, approvals, event protocol, and tool renderers.
5. Hybrid retrieval, reranking, citations, evidence sufficiency, and contradiction handling.
6. Governed memory, Bid Wiki, evidence graph, and Agent context assembly.
7. Workflow visualization driven by actual execution events and resumable runs.
8. Enterprise security, quota, cost ledger, observability, recovery, and operational runbooks.
9. Commercial account, trial, billing, email, retention, support, and plan enforcement flows.
10. A polished desktop/mobile product with a guided first-run sample project.
11. An end-to-end demo showing upload to readiness pack to requirement closure to reviewed export.
12. A release evidence pack containing test results, benchmark results, threat tests, recovery drills, screenshots, architecture diagrams, deployment instructions, and known residual risks.

## Phased Delivery and Gates

### Phase 0: Baseline and BidBench

- freeze the current behavioral baseline;
- create visible development fixtures and the annotation protocol for frozen and hidden sets;
- implement benchmark schema and runners;
- measure current pipeline and general-AI baseline.
- define a parser acceptance matrix for native PDF, scanned PDF, DOCX, spreadsheets, images, complex tables, damaged/encrypted files, and malicious uploads.

Gate: reproducible reports exist and expose current weaknesses.

### Phase 1: Requirement Ledger Foundation

- add shared provenance/assignment/claim trace models and BidPilot requirement extensions;
- implement extraction review, coverage, ownership, risk, and source inspection;
- produce a versioned Bid Readiness Pack with Word and spreadsheet outputs;
- add read-only Agent capabilities for the ledger;
- run a three-role acceptance scenario: bid manager assigns work, solution owner attaches evidence, reviewer rejects or closes the requirement.

Gate: the development sample can be processed and reviewed without drafting a document, and at least one representative ICP user validates time-to-readiness, omission usefulness, review effort, and willingness to continue using or paying for the closure workflow. Failure pauses later platform expansion for product correction.

### Phase 2: Unified Agent Runtime

- unify runtime contracts and event protocol;
- add capability registry and policy decisions;
- connect approval, usage, audit, trace, cancel, retry, and resume;
- remove split-brain execution paths or place them behind explicit adapters.
- enable Agent write capabilities only after the shared policy and capability contract is active.

Gate: assistant and workflow operations pass the same contract and policy tests.

### Phase 3: Retrieval and Evidence 2.0

- implement hybrid retrieval, fusion, reranking, locator validation, and contradiction checks;
- add retrieval evaluation and regression gates;
- prevent unsupported claims from final approval.

Gate: BidBench quality targets pass.

### Phase 4: Knowledge and Memory

- implement governed memory candidates;
- add project and organization Bid Wiki;
- add evidence graph and Agent context packs;
- integrate knowledge write-back with approval and audit.

Gate: reusable knowledge improves a second project without cross-project leakage.

### Phase 5: Enterprise and Commercial Hardening

- finish shared rate limiting, billing, quotas, retention, observability, backup, restore, and incident runbooks;
- complete team permissions and enterprise identity extension points;
- validate large bundles and concurrent users.

Gate: production-readiness, security, recovery, and cost reconciliation checks pass.

### Phase 6: Product and Release Closure

- refine navigation and all golden flows;
- verify desktop and mobile;
- run external-style acceptance with a non-developer user;
- generate the release evidence pack and deployment candidate.

Gate: the final completion audit has no unresolved P0/P1 issue and no unproven core claim.

## Stop Conditions

The strategy must be reconsidered if repeated evidence shows any of the following:

- BidPilot cannot beat a carefully prompted general-purpose model on completeness and traceability;
- users consume only a free report and will not pay for closure, collaboration, or governance;
- users export the requirement matrix and do not return to the system;
- organization knowledge setup costs more effort than it saves;
- collaboration features do not reduce follow-up and review labor;
- reliable source localization is not achievable for the target documents.

## Definition of Done

“Feature exists” is not done.

The goal is done only when:

- the golden user flow works end to end;
- table-stakes capabilities are production-quality;
- differentiating metrics beat the defined baselines;
- security, policy, cost, and recovery invariants are proven by tests;
- a new user can understand and use the product without developer intervention;
- the deployment candidate and evidence pack are reproducible from the repository;
- residual limitations are explicit and commercially acceptable.
