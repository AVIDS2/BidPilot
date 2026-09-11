# Frontend Experience Principles

## Goal

Define the user experience bar for `DocPilot` so the frontend is treated as a product surface, not just a shell around backend features.

This document exists to keep implementation from collapsing into a generic admin panel.

## Product posture

`DocPilot` should feel like a focused execution workbench for complex document delivery.

It should communicate:

- confidence
- clarity
- traceability
- operational depth

It should not feel like:

- a chat toy
- a CRUD-heavy internal admin console
- a visual clone of generic SaaS templates

## UX principles

### 1. Workbench over dashboard

The primary experience is a working surface, not a marketing dashboard.

Default screens should prioritize:

- current project context
- current execution state
- current evidence and review status
- next useful action

The Agent workspace uses two user-facing context surfaces:

- **Project workspaces** group related conversations under the project they work on;
  unscoped conversations remain under `个人会话`.
- **Work overview** shows the current project, active background work, recent
  work, and links back to the project or the related Agent conversation. It opens from the Agent
  top-right control as a compact shadcn `Popover` status card rather than a
  permanent pane. It is not a developer console: only actionable project and
  user-owned task status belongs here.
- Conversation actions use a single shadcn `DropdownMenu` per row rather than
  several always-visible icon buttons. The menu keeps pin, rename, and delete
  discoverable without competing with the conversation title.
- Chat history restores directly to the latest message. While the reader is at
  the bottom, new streamed content follows automatically; once the reader
  scrolls upward, the viewport is left alone and a single "回到底部" action is
  provided.
- The Agent's contextual right surface is one user-owned panel, not a second
  conversation. It uses the installed `Tabs` and `ResizablePanelGroup` to keep
  collaboration progress, response workflow, and attachment preview available
  as sibling pages. Desktop collapse/expand uses the panel's native imperative
  API so the surface remains mounted while it animates; on mobile the same tabs
  live inside the installed `Sheet`.
- A child Agent is a branch of the current Copilot process. It has runtime
  status and useful business progress, but no independent user history entry
  or synthetic chat message.
- Pending messages are visible as a real queue with two explicit semantics:
  `引导当前任务` sends an attachment-free instruction through Pi's native
  `steer` path while the current turn is active; `发送下一条` uses the normal
  durable-turn path after the current runtime has settled. Queue state is
  derived from the live response boundary and a rejected request stays in the
  queue instead of becoming a fake success state.

Runtime implementation details such as provider names, tool counts, MCP
registration, sandbox/network profiles, raw event payloads, and internal engine
names stay out of the user surface. They belong in the operations and
observability views. The overview must still be backed by live project/run APIs,
not demo counters or replay-only UI state.

### Product information architecture decision (2026-09-09)

The authenticated product is organized around the user's work, not around the
runtime that performs it.

Primary navigation has four jobs:

1. `总览`: what needs attention today and the next useful action.
2. `项目`: the portfolio of opportunities and active engagements.
3. `我的工作`: assigned reviews, approvals, failures, deadlines, and personal
   follow-ups.
4. `助手`: the conversational entry point for asking the Copilot to act in the
   current project context.

The project workspace owns the durable workflow tabs: overview, materials,
requirements, response, review, deliverables, and project knowledge. These are
facts and actions about one project and must not send a user to a generic Agent
page without preserving the project context.

The following surfaces are deliberately secondary:

- `知识库` is a cross-project index of source-backed project knowledge and
  published team methods. It is not a developer memory console.
- `收件箱` is a notification/attention surface and may be merged into `我的工作`;
  it must not expose broker or runtime queue terminology.
- `运行记录` is an administrator/recovery view, reachable from a failed or
  interrupted business object. It is not a customer-facing primary route.
- provider settings, webhooks, members, billing, and memory controls belong in
  a settings center with task-oriented labels.

No page should explain the implementation in its default copy. A user needs to
know what happened, what it affects, and what they can do next. Terms such as
`queued`, `queue`, `Mem0`, `checkpointer`, `Store`, `RuntimeRun`, and `embedding`
belong in diagnostics or documentation only.

### Memory control surface

The account/settings area must provide one `个性化与记忆` surface with:

- one global toggle for personal preference memory;
- a clear explanation that disabling it stops new personal-memory writes and
  recalls but does not delete existing records;
- a list of personal preferences with source conversation, last used time,
  scope, and delete/edit actions;
- `清除全部个人偏好` with a confirmation step and completion state;
- project knowledge and team methods linked to their project/workspace pages,
  not mixed into the personal list.

The UI should never claim that the assistant “remembers everything”. The four
engineering types map to the user terms `当前工作上下文`, `工作记录`, `项目知识`,
and `团队方法`; `用户偏好` is the only cross-project personalization layer.

The detailed runtime event view at `/runs` is an administrator-only diagnostic
surface. Ordinary users follow a task from the Agent conversation, project
workspace, or `我的工作` page and should never be sent to the raw event view.

The authenticated workbench uses one consistent navigation model: a desktop
sidebar can be collapsed with its existing control and restored by clicking the
visible Logo, while mobile replaces that sidebar with an accessible shadcn
`Sheet` opened from the topbar. Long workspace names must shrink with an
ellipsis instead of pushing controls out of the container.

Account and workspace settings should use the official shadcn composition already
installed in the application: line tabs for sections, cards for bounded settings
groups, `Field` for form rows, and `Avatar`, `Badge`, `Switch`, `Progress`,
`Skeleton`, and `Empty` for identity, preferences, usage, and async states. Use
the shared `Button` and menu primitives for actions instead of bespoke control
markup when the primitive already covers the interaction.

All new product UI should start from the installed Kiranism/shadcn components
and their documented composition. Local CSS is reserved for domain layout,
responsive geometry, and visual tokens; it must not replace an existing
`Tabs`, `Accordion`, `Dialog`, `Sheet`, `Field`, `Item`, `Empty`, `Select`, or
`Resizable` interaction with a bespoke control.

Theme choice uses the upstream Kiranism `ThemeSelector` and its registered theme
files. Do not invent a second palette picker or hard-code feature colors; the
selected theme is persisted through the existing active-theme cookie and applies
to the authenticated workbench and public marketing routes. The public
navigation follows the same upstream composition: the mode toggle is available
at every size, while the full theme selector follows the template's compact
screen behavior.

Every route, including the Agent transcript and public landing page, inherits
the active Kiranism theme tokens for background, foreground, primary, muted,
border, ring, and destructive states. Feature-specific styling may add layout
and domain status emphasis, but it must not replace the product palette with a
second light/dark skin or expose template implementation details to users.

### 2. Dense, but navigable

The product will carry a lot of information.

That means the UI should aim for:

- high information density
- strong grouping
- clear hierarchy
- low noise

Avoid wide empty layouts that waste space and force excessive scrolling.

### 3. Evidence must stay visible

Because the system is execution- and evidence-driven, the user should not lose access to:

- source context
- requirement mapping
- evidence links
- review decisions
- run history

The UI should support split panes, drawers, side panels, and version-aware detail views where needed.

### 4. Human review is first-class

The UX must not assume the model is always right.

The review experience should feel central, not bolted on.

This includes:

- draft vs approved states
- change reasoning
- evidence inspection
- comment and rejection flows
- rerun and compare flows

### 5. Responsive means adaptive, not shrunken

Responsive behavior should preserve intent, not merely compress layouts.

Desktop should be optimized for multi-pane work.
Tablet should preserve core review and drafting flows.
Mobile should support oversight, status checking, light review, and approvals, but does not need to expose every advanced authoring control.

### 6. Motion should explain structure

Use motion sparingly to clarify:

- pane transitions
- version switches
- review state changes
- step progression

Avoid decorative motion that adds delay or ambiguity.

Live indicators must be driven by real query freshness, Pi events, or a domain
state transition. A pulse, shimmer, spinner, or chart transition must never be
used to imply work that the service has not actually started.

### 7. Accessibility is part of credibility

The interface should satisfy practical accessibility expectations from the start:

- keyboard-accessible navigation
- visible focus states
- sufficient contrast
- reflow-friendly layout
- semantic form and dialog behavior

### 8. Loading and navigation should preserve context

The workbench must stay usable while a route chunk or server query is loading:

- keep the authenticated shell mounted during route-level lazy loading
- prefetch route chunks on navigation intent, including keyboard focus and touch
  press where possible
- distinguish loading from an actually empty result; never render a transient
  zero count or empty state as if it were business truth
- use the shared query cache for short-lived page transitions and keep visible
  prior data while a background refresh is in progress
- use shadcn `Skeleton` for structural loading placeholders and reserve motion
  for explaining a live workflow, upload, or state transition

The first implementation pass is frontend-owned. Dashboard, knowledge, and
project workspaces still have dependent query fan-out (for example readiness
per project or documents per bundle); backend aggregation and query-plan
measurement remain a separate performance follow-up rather than being hidden
inside route loading code.

## Layout strategy

### Primary shell

The frontend should use a workbench shell with:

- top-level project context
- left navigation for durable product areas
- central task surface
- right-side contextual detail or evidence panel when useful

### Preferred patterns

- resizable panes
- persistent tabs for major work areas
- drawers and sheets for secondary actions
- sticky section headers for long documents
- explicit empty, loading, error, and partial-success states

### Avoid

- modal-heavy workflows for primary tasks
- deeply nested navigation
- single-column everything layouts on desktop
- excessive dependence on hover-only affordances

## Responsive breakpoints by intent

### Desktop

- primary target for drafting, review, evidence inspection, and export preparation
- multi-column and multi-pane layouts encouraged

### Tablet

- preserve project context plus one major task surface
- secondary panes may collapse into drawers or tabs

### Mobile

- focus on status, alerts, approvals, and lightweight review
- do not force full drafting workflows into a cramped screen just to claim mobile completeness

## Visual system direction

The visual language should feel:

- clean
- deliberate
- technical
- sober, but not lifeless

Recommended characteristics:

- strong typography hierarchy
- restrained but distinctive accent usage

The public marketing page is a separate campaign surface from the authenticated
workbench. Its structure follows the MIT Open SaaS landing source: sticky
navigation that compresses into a floating bar, a product Hero, example/product
surfaces, capability sections, FAQ and Footer, with the mobile navigation in a
Sheet. The Wasp-specific router, auth and backend are intentionally excluded;
only the landing source structure is ported to Next and the current shadcn
components. The Kiranism semantic theme remains the authority for the
marketing page, authenticated shell, forms and workbench, so theme selection
changes the surface and primary color without importing a fixed black/purple
palette.
- token-based spacing and color system
- component states that clearly communicate draft, reviewed, approved, failed, and missing-evidence conditions

## Frontend quality bar

The frontend is not production-ready unless:

- key screens are responsive by intent
- interaction states are explicit
- review and evidence flows are understandable without explanation
- visual regressions are checked
- accessibility basics are covered in component and flow testing

## Tooling implications

To support this quality bar, the frontend should treat these as standard tools:

- `shadcn/ui` for open-code component foundations
- `Radix`-backed primitives for interaction correctness
- `Storybook` for component, screen, and state documentation
- `Playwright` for flow verification
- design tokens through CSS variables and Tailwind-driven styling
