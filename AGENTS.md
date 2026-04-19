# DocPilot Instructions

This repository is the planning and implementation home for `DocPilot`, with `BidPilot` as the first scenario package.

## Read before building

Before implementing or refactoring meaningful code, read:

- `docs/superpowers/specs/2026-04-18-docpilot-design.md`
- `docs/product/roadmap.md`
- `docs/product/mvp-scope.md`
- `docs/adr/0001-core-technology-stack.md`

## Primary stack

- Frontend: `TypeScript + React + Vite`
- UI: `Tailwind CSS + shadcn/ui + TipTap + React Flow`
- Backend: `Python + FastAPI + Pydantic v2 + SQLAlchemy 2`
- Jobs: `Celery + Redis`
- Data: `PostgreSQL + pgvector + MinIO/S3`

## Architecture rules

- Business truth lives in `PostgreSQL`, not in prompts, runtime memory, or agent state.
- `LangGraph` is an execution detail, not the control-plane source of truth.
- AI providers, parsers, retrievers, and external tools must stay behind adapters.
- Keep the codebase modular, but do not split into more services unless the architecture docs justify it.

## Tooling rules

- Do not guess third-party APIs, CLI flags, component props, or schema details when docs or tooling are available.
- Prefer `Context7` or official docs for library and framework questions.
- Prefer `shadcn` tooling for shadcn/ui work instead of hand-guessing component usage.
- After meaningful UI or interaction changes, verify with `Playwright` when the affected flow is runnable.
- Before schema-related changes, inspect migrations, models, or database tooling first.

## Preferred development loop

These are repository defaults for AI-assisted development. Treat them as strong preferences, not brittle hard gates:

1. Read the relevant project docs and phase plan before making non-trivial changes.
2. If a library API or integration detail is unclear, check `Context7`, project source, or official docs before coding.
3. For UI work with `shadcn/ui`, use `shadcn` tooling first and customize from there.
4. For backend or data work, check current models, migrations, and adapters before adding new structures.
5. After meaningful UI changes, run `Playwright` if the flow can be exercised locally.
6. If a detail is still uncertain, leave a small explicit TODO or note instead of inventing behavior.

## Scope control

- Do not expand beyond `BidPilot` until the existing roadmap phase justifies it.
- If a foundational architecture, stack, or ops behavior changes, update the relevant docs in `docs/`.
