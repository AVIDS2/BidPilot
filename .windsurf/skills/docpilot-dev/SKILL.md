---
name: docpilot-dev
description: Use this when implementing, refactoring, or debugging code in the DocPilot/BidPilot repository. It loads the project's stack, architecture constraints, required docs, and verification workflow.
---

# DocPilot Development Skill

## When to use

Use this skill for any meaningful implementation or refactor in this repository.

## Recommended reading

For non-trivial changes, start with these files:

- `docs/superpowers/specs/2026-04-18-docpilot-design.md`
- `docs/product/roadmap.md`
- `docs/product/mvp-scope.md`
- `docs/adr/0001-core-technology-stack.md`
- the relevant phase plan in `docs/superpowers/plans/`

## Working rules

- Keep business truth in `PostgreSQL`.
- Treat AI runtimes, parsers, retrievers, and providers as replaceable adapters.
- Do not introduce a new primary framework or language without updating docs and ADRs.
- Prefer verifying uncertain APIs, schema details, and component usage before implementing.

## Frontend workflow

- Use `React + Vite + TypeScript`.
- Prefer `Tailwind CSS + shadcn/ui`.
- Use `TipTap` for document editing surfaces and `React Flow` for graph-like workflow UI.
- Start `shadcn/ui` work from `shadcn` tooling when possible.
- Verify important UI flows with `Playwright` when they can be exercised locally.

## Backend workflow

- Use `Python + FastAPI + Pydantic v2 + SQLAlchemy 2`.
- Keep route handlers thin and put orchestration in services.
- Use `Celery` workers for long-running async tasks.
- Normalize provider-specific behavior behind adapters.
- Check models, migrations, and adapters before inventing new fields or integration surfaces.

## Verification

- Run the relevant local verification before claiming a change works.
- For UI changes, prefer `Playwright` or equivalent browser checks.
- For schema or data work, inspect migrations and schema before coding.
- If a tool is unavailable, fall back to source inspection and leave an explicit note instead of guessing.
