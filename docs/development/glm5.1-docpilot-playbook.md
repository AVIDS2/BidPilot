# GLM5.1 Development Playbook for DocPilot

## Goal

Give `Windsurf + glm5.1` a lightweight, project-specific workflow for `DocPilot` without over-constraining normal development.

This playbook is only for this repository.

## What this playbook optimizes for

- less API guessing
- less schema guessing
- fewer UI regressions
- faster use of project docs and existing tooling
- enough flexibility to keep shipping

## Default working style

Treat these as preferred defaults, not hard stop conditions:

1. Read the relevant project docs before non-trivial work.
2. If an API or tool usage is unclear, check docs before coding.
3. For `shadcn/ui` changes, start from `shadcn` tooling.
4. For schema changes, inspect migrations, models, and database structure first.
5. After meaningful UI work, run `Playwright` if the flow is runnable.
6. If a detail is still uncertain, do not invent it silently.

## Read first

Start with these files for meaningful changes:

- `AGENTS.md`
- `docs/superpowers/specs/2026-04-18-docpilot-design.md`
- `docs/product/roadmap.md`
- `docs/product/mvp-scope.md`
- `docs/adr/0001-core-technology-stack.md`
- the relevant phase plan in `docs/superpowers/plans/`

## Tool preference order

### Library and framework questions

Preferred order:

1. `Context7`
2. official docs
3. project source

Use this when:

- an API is unfamiliar
- a CLI flag is uncertain
- a provider integration is changing quickly

### shadcn/ui work

Preferred order:

1. `shadcn` tooling or MCP
2. existing project patterns
3. manual customization

Use this when:

- adding a new component
- checking props or composition patterns
- aligning a UI change with the existing stack

### Database and schema work

Preferred order:

1. migrations
2. SQLAlchemy models
3. Postgres MCP or direct schema inspection

Use this when:

- adding a table or field
- updating a model
- writing data-dependent backend logic

### UI verification

Preferred order:

1. `Playwright`
2. local manual smoke test

Use this when:

- the change affects interactions
- the change affects forms, tables, dialogs, navigation, or document workflows

## Suggested task loop

For most tasks, this sequence is enough:

1. understand the feature or bug scope
2. read the relevant docs and current code
3. verify uncertain APIs or schema details
4. implement the smallest coherent change
5. run the best available verification
6. summarize what changed and what was verified

## Good defaults for glm5.1

Use these habits:

- prefer existing patterns over new abstractions
- prefer adapters over provider-specific logic leaking inward
- prefer explicit notes over invented assumptions
- prefer small, reviewable changes over broad refactors

Avoid these habits:

- guessing library APIs
- inventing database fields
- hand-rolling `shadcn/ui` usage from memory
- claiming UI behavior works without checking it

## Example starter prompt for Windsurf

Use this as a lightweight opener when starting a new task in this repository:

```text
You are working only in the DocPilot repository.

Before coding, read AGENTS.md and the relevant product/architecture docs for this task.
Use light-touch repository defaults:
- check Context7 or official docs before using unfamiliar APIs
- use shadcn tooling first for shadcn/ui work
- inspect migrations/models before schema changes
- run Playwright after meaningful UI changes when the flow is runnable
- do not invent API or schema details silently

Keep changes aligned with the existing React + Vite, FastAPI, and PostgreSQL architecture.
Prefer small, verifiable changes and summarize what you verified.
```

## When to ignore the defaults

It is fine to skip one of the preferred tools when:

- the tool is unavailable
- the code path is too small to justify it
- the answer is already obvious from nearby project source

In that case, keep moving and note the fallback briefly.
