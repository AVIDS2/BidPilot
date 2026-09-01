# Frontend Application Architecture

## Goal

Define a frontend architecture that supports long-lived product quality, not short-term page assembly.

## Frontend stack decision

The frontend stack was updated on 2026-09-01 to:

- `TypeScript`
- `React 19`
- `Next.js 16 App Router`
- `Tailwind CSS v4`
- `shadcn/ui`
- `TanStack Query`
- Next.js routing and `nuqs` for URL state where useful
- `TipTap`
- `React Flow`
- `Storybook`
- `Playwright`

## Why this stack

### React 19

React 19 is stable and adds better support for async actions, optimistic updates, and form flows, which fits execution-heavy product surfaces well.

### Next.js App Router

Next is used as the presentation and same-origin transport edge, not as the
business backend. Its App Router provides route-level server rendering,
metadata and Route Handlers that forward authenticated REST/SSE requests to
the existing FastAPI control plane.

The business core remains Python-first. Next does not own PostgreSQL state,
provider keys, Pi sessions, tool authorization or workflow orchestration.

### Tailwind CSS v4

Tailwind v4 improves performance, simplifies setup, and moves toward CSS-first configuration, which is a good fit for a token-driven design system.

### shadcn/ui

`shadcn/ui` is the correct foundation for this project because it provides accessible, open-code building blocks instead of locking the product into a closed component package.

### TanStack Query

Use TanStack Query for server-state, caching, invalidation, and async data orchestration. Do not replace it with ad hoc fetch state or a heavy global-state workaround.

### Next routing and `nuqs`

Use the App Router for route structure and `nuqs` only for shareable filters,
selected tabs and pane state. Do not create a second client router inside the
Next app.

### Storybook

Use Storybook as a standard part of frontend development, not an optional nicety. It should document components, states, and screens in isolation.

## Frontend code structure

## Top-level layout

Preferred structure:

- `apps/web/src/app`
- `apps/web/src/features`
- `apps/web/src/components`
- `apps/web/src/lib`
- `apps/web/src/hooks`

The active Next application uses file-system routes and keeps domain state in
the existing API/Pi boundary. The active feature boundaries are:

```text
apps/web/src/
  app/                            # App Router pages and Route Handlers
    (app)/                        # authenticated product routes
    api/                          # same-origin auth and FastAPI BFF
  features/
    agent/                        # Pi runtime projection and Agent workbench
      state/agent-store.tsx       # client state fed by API/SSE contracts
      runtime/                     # event projection and transcript mapping
      components/                  # Agent timeline, approvals, actions, panels
      legacy/                      # unused assistant-ui experiment only
    bidpilot/                     # composed product primitives
  components/ui/                  # shadcn primitives
  components/                    # shell primitives shared by routes
  lib/                            # transport, auth, i18n, browser utilities
```

## Layer responsibilities

### `app`

Owns:

- app bootstrap
- providers
- router setup
- theme setup
- global layout shell

### `routes`

Owns:

- route trees
- route-level data loading hooks
- screen composition

Do not bury durable screens inside generic page folders with unclear ownership.

### `features`

Owns domain-specific UI and logic, such as:

- projects
- bundles
- requirements
- evidence
- drafting
- review
- exports
- audit

Each feature should contain:

- API query hooks
- feature-local components
- view models or mappers when needed
- story and test files where practical

### `components`

Owns reusable UI building blocks:

- shell primitives
- layout primitives
- common composed components
- shared forms
- tables
- states

Separate:

- low-level UI primitives
- higher-level product components

### `lib`

Owns shared technical utilities:

- API client
- query client
- route helpers
- schema helpers
- formatting utilities

Do not turn `lib` into a dumping ground for feature logic.

Agent event projection is deliberately not in `lib`: `RuntimeEvent` to
assistant-event mapping, transcript grouping, and Agent client state belong to
`features/agent`. The UI consumes the public runtime event contract (event id,
sequence, parent/child run relation, status and redacted summary); it never
infers execution from user message text or tool-name substrings.

The former assistant-ui experiment remains quarantined under
`features/agent/legacy` and is not part of the active Next route graph. The
production Agent surface is `features/agent`; the authenticated product shell
is `components/layout/app-shell.tsx` and uses Kiranism Sidebar/Sheet
primitives.

### Navigation and server-state loading

The active Next App Router keeps the authenticated shell mounted while route
content changes. TanStack Query owns server state and uses a short default
stale window; feature queries can override it for live execution surfaces. The
Agent's only lazy import is its composer bundle, and it has one bounded stale
chunk recovery path for browser sessions holding an obsolete HTML shell.

Screens must treat `isLoading`/`isPending` as a first-class display state. A
query-backed count is not `0` until its request has completed, and an empty
state is only rendered after the relevant dependent queries have settled.
This is a presentation and caching concern, not a replacement for measuring
slow API TTFB or reducing backend query fan-out.

The authenticated Next Workbench keeps one navigation model across breakpoints.
On desktop, Kiranism's Sidebar collapse trigger remains in the header; the
collapsed Logo is the accessible restore affordance. On mobile, the same
Sidebar becomes a shadcn `Sheet` opened by that header trigger. The browser
tab uses the current BidPilot Logo through Next's `app/icon.svg` convention.

## State strategy

### Server state

Use `TanStack Query` for:

- API data fetching
- invalidation
- optimistic mutation coordination
- background refresh where justified

### URL state

Use App Router search params or `nuqs` for:

- selected project context
- filters
- sort
- pane state when shareable
- tab state when meaningful to preserve

### Local UI state

Use local React state for:

- ephemeral form interaction
- disclosure state
- temporary editing affordances

Do not push purely local UI state into a global store.

### Global client state

Avoid introducing a broad global store by default.

Only add a dedicated client-state library if repeated cross-feature coordination clearly exceeds what router state, query state, and local state can manage cleanly.

## Component architecture

### Preferred hierarchy

1. design tokens and style primitives
2. `shadcn/ui` primitives and wrapped shared primitives
3. reusable product components
4. feature components
5. route screens

### Rules

- prefer composition over inheritance-style wrappers
- do not create dozens of one-off design abstractions too early
- do not scatter layout logic across unrelated leaf components
- keep feature state close to the feature boundary
- settings screens should compose the installed shadcn primitives for tabs,
  cards, fields, actions, and async states before adding local control markup
- server-backed settings should keep query keys scoped to their user or
  organization and update the shared query cache after mutations

## Screen architecture

The frontend should organize around durable screen types:

- project list and creation
- project workspace shell
- bundle and source document views
- requirement matrix
- drafting surface
- evidence inspection
- review and approval surface
- audit and run history
- export surface

Each screen should define:

- primary task
- main data dependencies
- empty state
- error state
- loading state
- success state

## Responsive architecture

Design responsive behavior at the layout-system level, not per component in isolation.

Preferred strategy:

- shell defines breakpoint behavior
- panes collapse to drawers or tab regions
- tables and matrices define alternate compact views
- action bars remain reachable without obstructing content

## Testing and documentation architecture

### Storybook

Every important shared component and feature state should be represented in Storybook.

Minimum story coverage:

- default state
- loading state
- empty state
- error state
- dense real-data state
- mobile or narrow viewport variant when meaningful

### Playwright

Use Playwright for route-level and multi-step flow verification.

### Accessibility

At minimum, validate:

- keyboard navigation
- dialogs and drawers
- focus management
- contrast-sensitive states
- layout reflow for smaller widths

## Design system discipline

The project should gradually build a real internal design system through:

- shared tokens
- shared shell patterns
- shared review and state components
- versioned Storybook documentation

The goal is not just visual consistency, but faster and safer product iteration.
