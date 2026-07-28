# Worktree Commit Plan

## Purpose

The current worktree contains interleaved production-readiness, agent-runtime,
LangGraph, domain-flow, test, documentation, and UI changes. This document
defines the review and commit boundaries required by P0-A1. It is a sequencing
plan, not evidence that any group has already been committed or deployed.

## Audit Snapshot

- audited: 2026-07-27
- branch at audit: `codex/frontend-v2-rebuild`
- staged changes: none
- scope observed: 211 changed paths across API, Worker, contracts, docs, ops,
  migrations, fixtures, and web
- rule: each group below must pass its stated verification before it is staged;
  do not use `git add .` for this worktree.

## Explicit Exclusions

The following paths are outside product commit groups until their owner reviews
them independently:

- `.codegraph/daemon.pid` deletion: generated local process state.
- `.claude/plugins/cache/anysearch-skill`: tool/plugin cache state.

No `.env`, provider key, build output, browser artifact, or screenshot path was
found among the current untracked files during this audit. That check does not
replace a staged-diff secret scan before each commit.

## Commit Groups

| Order | Proposed commit scope | Includes | Required verification |
| --- | --- | --- | --- |
| 1 | `feat(schema): durable runtime and bid-domain migrations` | `services/api/alembic/versions/`; matching model/contract changes needed for migration health | fresh DB `upgrade head`; existing DB upgrade; `scripts/verify_migration_health.py` |
| 2 | `feat(harness): durable assistant runtime and approvals` | API `assistant/`, `runtime/`, `agent/`; runtime contracts; API runtime/assistant tests; runtime event lineage migration | API runtime/assistant tests; request replay, approval, cancel, reconnect regression paths |
| 3 | `feat(workflow): governed LangGraph execution and review resume` | Worker graph, execution, runtime events, tasks, retrieval; API drafting/workflow bridge; Worker tests; workflow-task/review-version migrations | Worker test suite; duplicate resume does not create another version; durable event replay |
| 4 | `feat(knowledge): document ingestion, requirements, evidence, response plans` | API bundles/documents/requirements/response-plans; worker parser/ingest/retrieval; shared document/response-plan contracts; related migrations/tests | parse/retry lifecycle, tenant isolation, requirement lineage, evidence locator validation |
| 5 | `feat(governance): review, export, usage, and organization control plane` | API review/deliverables/versions/export/access/billing/organizations; review/export contracts, migrations, tests | reject/redraft/approve path; approved-only export; organization and usage regression tests |
| 6 | `chore(ops): reproducible local and production readiness` | compose/deploy/Docker/env example, readiness scripts, CI workflow, Python/Node lockfiles and package manifests | `uv sync --all-packages --locked`; API/Worker checks; `pnpm install --frozen-lockfile`; web lint/type/test/build |
| 7 | `docs(product): architecture, demo, operations, fixtures, and learning record` | README, `docs/`, `sample-data/`, benchmark documentation | link/path scan; no credential-shaped strings; golden-path docs match routes/events |
| 8 | `refactor(web): assistant runtime surface and quality gates` | `apps/web/` and its lockfile changes only | web lint, typecheck, Vitest, production build, desktop/mobile visual QA |

## Migration Ownership Map

- runtime and event lineage: `b0c1d2e3f4a5`
- reviewed-version and redraft governance: `b1c2d3e4f5a6`, `b2c3d4e5f6a7`
- document ingestion and retry lifecycle: `c3d4e5f6a7b8`, `fd2e3f4a5b6c`
- requirement and evidence boundaries: `d5e6f7a8b9c0`, `e6f7a8b9c0d1`
- response plans and exports: `fb0c1d2e3f4`, `fc1d2e3f4a5b`
- provider, workspace, billing, and organization controls: existing modified
  migrations `ab1...` through `fa0...`

## Commit Procedure

1. Review a group with `git diff -- <paths>` and run its verification before
   staging.
2. Stage only explicit paths for that group. Re-run a secret scan on the staged
   diff, then commit with the proposed scope.
3. Re-run the full API/Worker/Web baseline after group 6 and before any release
   rehearsal.
4. Keep P0-D6 deployment rehearsal and P0-E4 public-demo hygiene as separate
   approval-gated operations. They are not satisfied by local commits.

## Current Status

The audit snapshot above remains a historical record from 2026-07-27. Its
commit boundaries were executed on 2026-07-28 without using `git add .`:

| Order | Commit | Result |
| --- | --- | --- |
| 1 | `6d96ded` | Durable bid-domain contracts and migration health |
| 2 | `fabc241` | Governed Assistant Harness, approval, audit, and SSE runtime |
| 3 | `0122efb` | LangGraph workflow, evidence binding, and review resume |
| 4 | `ecfc233` | Document, requirement, and response-plan API boundaries |
| 5 | `8fe313f` | Tenancy, billing, quality, and runtime governance controls |
| 6 | `775368d` | CI, local/production readiness, release checks, and deployment safeguards |
| 7 | `5539a29` | Traceable synthetic demo material pack |

The documentation-only group was committed separately as `c5b0c1e` so that
frontend reconstruction work remains outside this backend closure. No public
deployment, VPS mutation, or remote push is implied by any of the commits
above.
