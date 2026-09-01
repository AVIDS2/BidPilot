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
  work, and links back to project or run details. It is not a developer console.
- Conversation actions use a single shadcn `DropdownMenu` per row rather than
  several always-visible icon buttons. The menu keeps pin, rename, and delete
  discoverable without competing with the conversation title.
- Chat history restores directly to the latest message. While the reader is at
  the bottom, new streamed content follows automatically; once the reader
  scrolls upward, the viewport is left alone and a single "回到底部" action is
  provided.

Runtime implementation details such as provider names, tool counts, MCP
registration, sandbox/network profiles, raw event payloads, and internal engine
names stay out of the user surface. They belong in the operations and
observability views. The overview must still be backed by live project/run APIs,
not demo counters or replay-only UI state.

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
