# BidPilot Operating Workbench Plan

> 本文保留早期“项目工作台”与 Agent 运行时设计决定。租户产品侧的完整信息
> 架构、页面职责和迁移顺序以
> [租户产品侧前端蓝图](2026-08-07-bidpilot-tenant-frontend-blueprint.md) 为准。
> Agent 是全平台的自然语言操作入口，不是需要被边缘化的独立功能，也不是
> 客户侧导航的中心。

## Decision

BidPilot is an enterprise tender-response operating system. The Agent is a
natural-language entry point into that system, not the system's only working
surface. Business truth remains in PostgreSQL and every important task must be
visible, editable, reviewable, and resumable without returning to chat.

This replaces the former page-by-page list/detail framing with a tender
lifecycle workbench. It follows the durable task and source-backed artifact
principles found in the local OpenBidKit architecture study, while keeping
BidPilot's SaaS tenancy, RBAC, audit, and LangGraph workflow boundaries.

## User Ownership

| Moment | Human operator | Workflow / Agent |
| --- | --- | --- |
| Opportunity qualification | Decide whether to bid, owner, deadline, priority | Extract notices, flag missing facts, propose plan |
| Source ingestion | Upload, classify, correct source metadata | Parse/OCR, detect duplicates, build evidence cards |
| Response planning | Assign owners, approve outline and compliance approach | Map requirements to sections, expose gaps and dependencies |
| Authoring | Edit content and approve changes | Draft from cited evidence, verify coverage, request approval |
| Review and delivery | Resolve issues, approve final package, export | Run checks, prepare deliverables, retain audit history |

The UI must always deep-link an Agent result to one of these human work
surfaces. A chat response without an inspectable artifact is not a completed
business action.

## Product Surfaces

### 1. Portfolio and opportunity intake

`/projects` becomes an opportunity portfolio, not a passive project list.
It supports importing an RFP, creating an opportunity, choosing go/no-go,
setting deadline/owner/priority, and viewing readiness/risk at a glance.

### 2. Project workspace

Each project has one persistent header and horizontal work tabs:

`Overview | Materials | Requirements & compliance | Response plan | Sections & evidence | Reviews | Deliverables`

- **Overview**: deadline, ownership, readiness, blocking risks, recent work,
  and next actions.
- **Materials**: upload, OCR/parse status, source preview, classification,
  duplicate handling, and explicit "add to project" actions.
- **Requirements & compliance**: extracted requirement table, owners,
  evidence/section mapping, status, and unresolved questions.
- **Response plan**: outline, section owners, dependencies, milestones, and
  a controlled start/resume workflow action.
- **Sections & evidence**: editable section content, cited evidence, compare
  versions, checkpoint/revert, and evidence coverage.
- **Reviews**: assign/review/resolve collaboration work; this is a human queue,
  not a read-only section index.
- **Deliverables**: configure package composition, run pre-export checks,
  export, and preserve released versions.

### 3. Cross-project operations

- **My Work**: actions assigned to the signed-in person, approvals, due work,
  and mentions.
- **Knowledge**: reusable source-backed assets; operators can upload,
  classify, merge, retire, and inspect provenance.
- **Runs**: operational health, retries, checkpoints, and trace inspection.
  It is an exception and observability surface, not the primary way to advance
  an RFP.
- **Dashboard**: active deadline, readiness, compliance, review, and delivery
  risk signals. Metrics only come from real records; zero-data states explain
  the next operational action.

### 4. Organization settings

One settings center with horizontal tabs:

`Organization | Members & roles | AI connections | Skills & MCP | Templates & brand | Security & audit | Usage`

AI providers are one tab, never the entirety of Settings. Skills/MCP exposes
server health, allowed capabilities, scopes, and last failure without exposing
secrets.

## Agent and Workflow Contract

1. Harness resolves intent, reads current project/context, and invokes a
   governed capability or starts/resumes a named LangGraph workflow.
2. Long work uses named persisted stages: `research -> ingest -> parse ->
   extract -> plan -> draft -> verify -> review -> deliver` as applicable.
3. Each stage writes durable artifacts and RuntimeEvents first, then emits SSE.
   A refresh replays the same event tree; no frontend reconstruction guesses
   hierarchy.
4. Skills/MCP are progressive-disclosure extensions. They may search or read
   under an allowlist; project writes still pass through platform capability,
   RBAC, approval, audit, and artifact validation.
5. Search is evidence, not prose: the trace shows a bounded list of real
   result URLs/titles/snippets, and selected sources can be imported into
   Materials as explicit actions.
6. Provider/model failures leave the completed stage tree intact and report a
   retryable failure state. They do not erase attachment context or force
   background status to remain "running" forever.

## Build Sequence

### P0: make the Agent trustworthy

- Durable event tree, replay, source cards, attachments, queue controls,
  cancellation, timeouts, and explicit terminal states.
- Route research/import through bounded capability adapters, and link each
  completed action to a project artifact.
- Replace model-failure black boxes with provider diagnostics, safe retry, and
  resumable workflow state.

### P1: build the real project workspace

- Materials, requirements/compliance, response planning, sections/evidence,
  reviews, and deliverables are editable, API-backed work surfaces.
- Convert the current read-only list/detail pages into the tabs above. Do not
  remove routes until their functional replacements exist.

### P2: organization operating system

- My Work assignments, configurable review routes, reusable knowledge library,
  delivery controls, dashboard signals, and consolidated settings center.

## Design Acceptance Rules

- Use the shared Linear-derived shell and tokens; no page-local font stack,
  raw purple focus treatment, or full-height decorative list rows.
- Use shadcn primitives where present for controls, overlays, tables,
  scroll areas, tabs, dialogs, and resizable panels. Compose them with the
  shared workbench styles instead of inventing a second visual language.
- A page uses borders only to establish a real containment or data boundary;
  hierarchy comes first from alignment, whitespace, type scale, and local
  navigation.
- Headers and local tabs stay fixed; data regions scroll locally. Every empty
  state provides the next valid action.
- Desktop and mobile visual checks are required after a meaningful UI change.

## Research Inputs

- `docs/research/2026-07-22-openbidkit-source-architecture-study.md`
- OpenBidKit source architecture (persistent task snapshots, document-backed
  artifacts, staged workflows)
- Loopio and Responsive public RFP workflow guidance (project ownership,
  content library, review workflow)
- Resend product and design references (dense operational navigation, data
  states, local controls, restrained border use)
