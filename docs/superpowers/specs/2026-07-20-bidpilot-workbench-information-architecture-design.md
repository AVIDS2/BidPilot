# BidPilot Workbench Information Architecture v1

## Status

- Date: 2026-07-20
- Status: Approved implementation slice
- Scope: authenticated product navigation and the first independent Agent
  workspace. This is not a generic workflow-builder redesign.

## Problem

The current authenticated shell exposes Dashboard, Projects, Settings, Pricing,
Docs, Teams, and Invitations as peer sidebar items. Most real bid work is then
hidden in a large set of project-detail tabs. This creates three failures:

1. the product looks like an account/settings site with one useful page;
2. the governed Agent is visually a constrained side panel instead of a
   first-class operating surface;
3. requirements, knowledge, runs, review, and deliverables do not have an
   obvious product home even though they are the domain's core artifacts.

BidPilot must expose the work loop before administration:

`project -> readiness -> evidence -> workflow -> review -> deliverable`.

## External Product Lessons

This is product-structure research, not an attempt to clone another product.

- [Microsoft Copilot Studio](https://learn.microsoft.com/microsoft-copilot-studio)
  separates creating agents/workflows, testing/evaluating them, administering
  access and policy, and publishing them. Build, evaluate, and administer are
  different jobs.
- [Dify Knowledge](https://docs.dify.ai/en/cloud/use-dify/knowledge/readme)
  treats knowledge as a dedicated product surface with ingestion and retrieval
  controls, rather than as hidden chat context.
- [Dify monitoring integration](https://docs.dify.ai/en/cloud/use-dify/monitor/integrations/integrate-aliyun)
  records workflow/node/model/tool/retrieval details as observable execution
  data, not as a chat transcript.
- [LangSmith Evaluation](https://docs.smith.langchain.com/evaluation/concepts)
  separates offline evaluation, online monitoring, datasets, and human feedback
  into a continuous quality loop.

The BidPilot translation is deliberately domain-specific: project work is the
primary surface; requirements and evidence are the execution spine; the Agent
is an operator over those surfaces; configuration and pricing are secondary.

## Information Architecture Decision

### Workbench navigation

The authenticated navigation is grouped into three intent-based areas.

| Group | Route | User job | Initial delivery state |
| --- | --- | --- | --- |
| Workbench | `/dashboard` | See portfolio health, blockers, onboarding, and next action | Existing dashboard, improved over time |
| Workbench | `/agent` | Direct the governed BidPilot operator across platform capabilities | Delivered in this slice |
| Workbench | `/projects` | Enter or create a bid workspace | Existing project portfolio |
| Execution | `/requirements` | Work across the Requirement Ledger with a project filter | Next slice; no empty placeholder link before implementation |
| Execution | `/knowledge` | See project-level shared knowledge health and open the project Bid Wiki | Delivered: bounded, permission-scoped portfolio index |
| Execution | `/runs` | Inspect active and historical Agent and workflow runs | First aggregate execution slice |
| Execution | `/reviews` | Resolve approvals, requirement disputes, and review work | Next slice; no empty placeholder link before implementation |
| Execution | `/deliverables` | Inspect export readiness and final outputs | Next slice; no empty placeholder link before implementation |
| Administration | `/settings/providers` | Manage model connections and controlled usage | Existing |
| Administration | `/admin/teams` | Manage invited collaborators | Existing, permission-scoped |

`Pricing` and public `Docs` remain reachable through account/public navigation;
they do not occupy primary workbench real estate. Global user administration
remains restricted to platform administrators and is not a normal team-work
entry point.

### Project detail navigation

Project detail remains the place to inspect project-local data. It must not be
the only way to discover the domain. Existing tabs are retained during the
transition, but future global surfaces will deep-link back to the appropriate
project and tab rather than duplicate business state.

## Run Center v1

`/runs` is the first aggregate execution surface. It exists because a team
cannot operate a governed Agent system by opening each project one at a time
and guessing which task is active, waiting for approval, or failed.

It is intentionally a **run center**, not a generic workflow builder:

- one row is a durable `RuntimeRun`, whether it originated from an Agent turn
  or a long-running LangGraph workflow bridge;
- rows show only project name, run kind, engine, lifecycle status, time, and
  the last already-redacted public event summary;
- selecting a row replays the same durable runtime events used by the Agent
  timeline; it never reads checkpoint tables, model traces, prompts, raw tool
  output, provider diagnostics, or credentials;
- a project row deep-links to that project's workbench. The center does not
  duplicate requirement, evidence, review, or deliverable business state.

### Aggregate authorization contract

The API list is not an organization-wide data leak:

1. Every row must belong to the caller's active organization.
2. Project-scoped rows are visible only when the caller has `project.read` for
   that project. Platform administrators retain the existing audited
   organization-admin project bypass.
3. A non-project Agent run is visible only to its initiating user, except for
   the existing platform-admin operator view.
4. The list is bounded and ordered by newest durable record. It never returns
   input JSON, result JSON, policy snapshots, provider configuration IDs,
   trace IDs, error internals, or event payloads.

The public list contract therefore has a separate schema from the internal
runtime model. It deliberately cannot become a convenient debugging endpoint.

### Initial user flow

1. Open **Runs** to see active, waiting-for-approval, failed, and recent work
   across projects the user can access.
2. Filter locally by visible lifecycle state; select a run for a safe replay of
   its public event timeline.
3. Navigate to the linked project for artifact work, or open the Agent
   workspace to continue the conversation.

### Acceptance criteria

- A contributor cannot enumerate another project's runtime row, event summary,
  or global Agent run.
- A platform admin sees the same project-run scope as the established access
  service permits.
- The dashboard reuses the bounded aggregate query rather than making a
  per-project N+plus-one run request.
- Empty, mobile, and populated desktop layouts do not collapse cards or force
  horizontal scrolling.

## Knowledge Portfolio v1

`/knowledge` is an aggregate discovery surface for the governed project Bid
Wiki. It is intentionally not a global knowledge graph, organization-wide RAG,
or a place to read record bodies.

- the aggregate API starts from the established project-access service and
  excludes deleted or inaccessible projects;
- each row exposes only project identity, active project-shared memory count,
  an authorization-aware proposal count, and safe compilation lifecycle
  metadata;
- every row deep-links to that project's Knowledge tab, which remains the only
  place for memory bodies, citations, evidence maps, proposals, and retrieval;
- the Agent can list the same safe metadata to help select a project, but it
  never injects a cross-project portfolio result into model context.

The project Knowledge tab now receives its bounded Evidence Map as a separate,
server-authorized provenance projection. It shows only active project-shared
Bid Wiki records and opaque source nodes joined by `cites`; it is not yet an
LLM-derived entity graph or a global RAG explorer.

This preserves the distinction between portfolio discovery and
project-authorized recall.

## Agent Workspace v1

`/agent` is an independent full-page Operator workspace. It shares the same
`AIAssistantProvider`, conversation records, SSE events, approvals, attachment
staging, model selection, reasoning effort, and approval mode as the optional
side panel.

It is not a second chat implementation.

### Required behavior

- A conversation begun in the side panel continues in `/agent`, and vice versa.
- Project-detail routes bind their project identifier into the shared Assistant
  context. Global routes clear that binding unless `/agent?project=<id>` makes
  an explicit target intentional; a previous project's authority must not leak
  into a new global task.
- The user sees the same chronologically ordered tool activity, approvals,
  workflow status, messages, attachments, and recovery controls.
- Creating a project or demo workspace navigates to the created project so the
  user sees the durable outcome rather than a stale portfolio count.
- Opening `/agent` never requires a model provider configuration merely to
  inspect history, use deterministic platform capabilities, or approve an
  existing action.
- The side panel remains a contextual shortcut outside `/agent`; `/agent`
  suppresses the duplicate floating/panel instance.
- The full page uses the current product component tree. No fake dashboard,
  copied assistant state, or synthetic tool rows are allowed.

### Layout

Desktop: bounded message column with a persistent header, full-height timeline,
and bottom composer. Conversation history is an overlay or left rail only when
opened; it may not shrink the composer into an unusable column.

Mobile: one column, no nested fixed-height panels, safe-area-aware composer,
and an overlay history sheet.

### Visual direction

- restrained neutral surfaces with the existing BidPilot brand accent;
- strong typographic hierarchy and compact user-facing action summaries;
- status color communicates state, never decoration;
- ReactBits/Motion effects may indicate a new state or active run, but never
  obscure content, introduce neon borders, or keep non-actionable elements
  animating indefinitely.

## Delivery Sequence

1. Add `/agent` and reuse the current Assistant component through an explicit
   workspace variant.
2. Suppress the duplicate side panel/floating trigger while `/agent` is active.
3. Group the sidebar around real work and remove Pricing/Docs from primary
   authenticated navigation.
4. Add browser and component tests proving cross-surface conversation reuse,
   project-creation navigation, mobile-safe layout, and no full-page reload.
5. Implement the global Requirements, Knowledge, Workflows, Reviews, and
   Deliverables pages only after their aggregate APIs and authorization rules
   exist. Each must read real product data and deep-link to project context.

## Non-Goals

- No generic no-code workflow canvas.
- No fake aggregate counts or mock activity cards.
- No second assistant backend, state store, or conversation schema.
- No broad visual rebrand or unrelated marketing-page restyle.
- No change to LangGraph workflow semantics or provider controls in this UI
  slice.

## Acceptance Criteria

1. Authenticated users can visit `/agent` directly and use the existing
   assistant conversation state.
2. `/agent` renders one Assistant instance, while other routes retain the
   optional side panel.
3. The sidebar foregrounds Dashboard, Agent, and Projects; public Docs/Pricing
   do not appear as primary work links.
4. Every navigation item in this slice points to a real usable screen.
5. Existing assistant tests, TypeScript, production build, and a Playwright
   browser check pass.
6. No raw tool payload, provider credential, or model API key becomes visible
   through the new surface.
