# Project Evidence Map

## Why This Slice Exists

The project Knowledge tab previously derived a React Flow visualization by
joining the memory ledger and citations already loaded in the browser. That
looked like a graph, but it did not establish a server-side access or lifecycle
contract and risked being mistaken for an LLM-derived knowledge graph.

## Delivered Boundary

- Added `GET /memory/evidence-map` for exactly one authorized project.
- The query admits only active, non-expired, non-deleted
  `project_shared` memory records and their validated source links.
- The response is bounded and reports truncation.
- It uses opaque source-node ids and returns no memory body, raw source id,
  locator, embedding, structured data, or model metadata.
- The Knowledge tab now renders the server projection separately from the
  ledger, with explicit loading, empty, error, and truncation states.

## What It Is Not

This is a small provenance map: `memory -- cites --> source`. It does not
assert factual support, synthesize entities or relations, become an
organization-wide graph, or enter Agent/Workflow model context.

## Verification

- `uv run --directory services/api pytest --noconftest tests/memory/test_commands.py -q`:
  `10 passed`.
- `pnpm --filter @docpilot/web test -- --run
  src/features/projects/tabs/knowledge-tab.test.tsx
  src/features/knowledge/knowledge-portfolio-page.test.tsx`: `5 passed`.
- `pnpm --dir apps/web exec tsc --noEmit` and
  `pnpm --filter @docpilot/web build` passed.
- API `compileall`, targeted Ruff, and `git diff --check` passed. Windows
  line-ending notices from unrelated pre-existing worktree files remain
  warnings only.

## Next Gate

Before writing `MemoryEntity` or `MemoryRelation`, define typed reviewed
proposals, source requirements, canonicalization, lifecycle invalidation,
frozen precision/merge/contradiction/isolation fixtures, and a user-decision
metric that justifies the graph.
