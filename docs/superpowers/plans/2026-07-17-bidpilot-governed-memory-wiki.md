# BidPilot Governed Memory and Bid Wiki Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a versioned, evidence-backed memory ledger and Bid Wiki that an authorized assistant and workflow can read safely and write only through governed proposals.

**Architecture:** PostgreSQL holds memory records, evidence links, graph projections, compilation runs, and audit truth. Retrieval 2.0 indexes approved memory records with the same profile isolation used for document chunks. LangGraph receives a bounded context pack and emits typed proposals; it does not become the memory database.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, PostgreSQL/pgvector/pg_trgm, Celery, LangGraph PostgresSaver, React, React Flow, pytest.

**Reference design:** `docs/superpowers/specs/2026-07-17-bidpilot-governed-memory-wiki-design.md`

## Implementation status (2026-07-17)

Core deliverables of Tasks 1 through 7 are implemented and covered by API, Worker, and web tests.
Task 8 now includes the redacted MemoryBench evaluator, operations/secrets
documentation, and full local regression evidence. The following items remain
intentionally open before production rollout:

- A successful independent code-review verdict; a Claude CLI attempt timed out
  without returning a verdict and is not counted as review evidence.
- A production credential-rotation and migration window for the new readiness
  gate; the existing VPS must not be restarted with new credentials until the
  database, MinIO, and Redis credentials have been rotated through their
  administrative paths.
- Optional 3D graph rendering. It is deferred until approved entity/relation
  projections have enough real source-backed data to justify it.
- Authenticated backend-flow Playwright coverage and visual assertions beyond
  semantic browser checks from a safe browser environment. Desktop Chromium
  and Pixel 7 now verify the public auth/pricing routes;
  route-level splitting separates public pages, the authenticated workspace
  shell, and assistant UI; Shiki uses a fine-grained browser bundle and the
  production build no longer reports a large-chunk warning.

---

## File map

- `packages/contracts/models.py`: durable ledger, evidence, entity/relation, and compilation models.
- `services/api/alembic/versions/<revision>_add_governed_memory_wiki.py`: additive schema/index migration.
- `packages/contracts/memory.py`: framework-neutral record, proposal, citation, and context contracts.
- `packages/contracts/memory_repository.py`: authorized lexical/vector candidate queries.
- `packages/contracts/memory_service.py`: scope filtering, version filtering, packing, and provenance assembly.
- `services/api/app/memory/*`: API authorization boundary, command/query services, and schemas.
- `services/worker/app/execution/memory.py`: compiler and profile-aware memory indexing task.
- `services/worker/app/graph/nodes/{memory_context,memory_proposals}.py`: LangGraph adapters only.
- `services/api/app/assistant/*`: assistant tools use context packs and create proposals rather than direct permanent writes.
- `apps/web/src/features/projects/tabs/knowledge-tab.tsx`: ledger, review queue, evidence inspection, and later graph projection.
- `services/api/app/evaluation/memory_metrics.py`: MemoryBench metrics and frozen-fixture validation.

## Task 1: Define contracts and failing scope tests

**Files:**
- Create: `packages/contracts/memory.py`
- Modify: `packages/contracts/__init__.py`
- Test: `services/api/tests/memory/test_contracts.py`

- [ ] Write tests that reject a project-shared record without a project id, a user-private record without an owner id, a system proposal without evidence ids, invalid scope/kind/status, and a context item lacking provenance.
- [ ] Run `uv run --directory services/api pytest tests/memory/test_contracts.py -q` and verify it fails before the contracts exist.
- [ ] Define `MemoryScope`, `MemoryKind`, `MemoryStatus`, `MemoryProposal`, `MemoryCitation`, `MemoryContextItem`, and `MemoryContextPack` as `extra='forbid'` Pydantic models. Keep title/body/JSON sizes bounded and require a deterministic `memory_version` in each pack.
- [ ] Export only the stable public contracts from `packages/contracts/__init__.py`.
- [ ] Rerun the test and verify it passes without FastAPI or LangGraph imports.

## Task 2: Add additive ledger and graph-projection schema

**Files:**
- Modify: `packages/contracts/models.py`
- Create: `services/api/alembic/versions/<revision>_add_governed_memory_wiki.py`
- Test: `services/api/tests/memory/test_memory_migration.py`

- [ ] Write a PostgreSQL migration test that asserts every memory table, scope/status index, provenance FK, project/profile vector index, and deleted-record filter index exists.
- [ ] Run the migration test against `docpilot_migration_test` and verify it fails before the migration.
- [ ] Add `MemoryRecord`, `MemoryEvidenceLink`, `MemoryEntity`, `MemoryRelation`, and `MemoryCompilationRun` with explicit organization/project/user foreign keys, lineage IDs, timestamps, and no JSON-only authorization fields.
- [ ] Add an additive migration. Existing database content must not be rewritten; new semantic indexes are partial on active, non-null-vector records only.
- [ ] Run `uv run --directory services/api alembic upgrade head` against the isolated database and rerun migration tests.

## Task 3: Implement authorized memory ledger commands and audit trail

**Files:**
- Create: `services/api/app/memory/{schemas.py,repository.py,service.py,router.py}`
- Modify: `services/api/app/main.py`
- Modify: `services/api/app/access/service.py`
- Test: `services/api/tests/memory/test_commands.py`

- [ ] Write tests for user-private create/read/delete, project shared proposal/approval, contributor denial for activation, organization isolation, supersede lineage, and deletion tombstones.
- [ ] Run the command tests and verify they fail because the router/service is absent.
- [ ] Add capabilities `memory.read`, `memory.propose`, and `memory.approve`; grant only owner/manager approval rights. Resolve project access before every query or command.
- [ ] Implement commands `create_manual_memory`, `propose_memory`, `approve_memory`, `reject_memory`, `supersede_memory`, and `delete_memory`. Each command writes a clear audit event and returns safe record summaries.
- [ ] Ensure delete clears active embedding fields and prevents future retrieval while keeping authorized audit lineage.
- [ ] Rerun command tests and verify all scope and audit assertions pass.

## Task 4: Add profile-aware memory retrieval and context packing

**Files:**
- Create: `packages/contracts/memory_repository.py`
- Create: `packages/contracts/memory_service.py`
- Create: `services/api/app/memory/embedding.py`
- Test: `services/api/tests/memory/test_context_pack.py`
- Test: `services/worker/tests/memory/test_memory_indexing.py`

- [ ] Write tests covering same-profile dense matching, lexical fallback with no provider, bounded context ordering, expiry/supersede/deletion filtering, private-project isolation, and provenance retention.
- [ ] Run the tests and verify they fail before retrieval implementation.
- [ ] Reuse `embedding_config` and Retrieval 2.0 outcome rules. A failed memory embedding never clears a good prior embedding or activates an unindexed record.
- [ ] Build `build_memory_context_pack` with authorization first, then candidate retrieval, then a deterministic token/record budget. It must return an explicit degradation reason rather than fabricated memory.
- [ ] Rerun tests against the isolated PostgreSQL database.

## Task 5: Compile proposals from project evidence without autonomous activation

**Files:**
- Create: `services/worker/app/execution/memory.py`
- Modify: `services/worker/app/tasks.py`
- Create: `services/worker/tests/memory/test_compilation.py`
- Modify: `services/api/app/bundles/service.py`

- [ ] Write tests that a compilation task accepts only authorized bundle/project input, does not parse source documents again, creates proposals with source locators, never directly activates a non-deterministic fact, and records a compilation run.
- [ ] Run tests and verify they fail before the task exists.
- [ ] Implement `worker.compile_bid_wiki` as a bounded worker task. It consumes Retrieval 2.0 evidence and existing active records, emits typed proposals, indexes them safely, and records safe failure categories.
- [ ] Make source-bundle processing enqueue compilation only after successful parsing/indexing and only when the project policy enables it. Do not charge a hidden extra model call without a visible usage event.
- [ ] Rerun tests and verify no existing `KnowledgeChunk`, `RequirementItem`, or source document is recreated.

## Task 6: Integrate assistant and LangGraph through context packs and HITL

**Files:**
- Modify: `services/api/app/assistant/{service.py,runtime.py,tools.py}`
- Create: `services/worker/app/graph/nodes/memory_context.py`
- Create: `services/worker/app/graph/nodes/memory_proposals.py`
- Modify: `services/worker/app/graph/{builder.py,state.py}`
- Test: `services/api/tests/assistant/test_memory_tools.py`
- Test: `services/worker/tests/memory/test_graph_memory_nodes.py`

- [ ] Write tests that an assistant can read only authorized context, asks for confirmation before remembering a user preference, emits a proposal instead of claiming memory was saved, and resumes an approved write idempotently.
- [ ] Run tests and verify they fail before the new tools/nodes exist.
- [ ] Add `search_bid_wiki`, `propose_memory`, `inspect_memory_source`, and `forget_memory` as policy-governed tools. Tool output contains a user-facing summary and citations, never hidden reasoning or raw provider output.
- [ ] Add `load_memory_context` before drafting/planning and `propose_memory_updates` after a successful, evidence-backed result. Compile these nodes with the existing Postgres checkpointer and require a stable thread id.
- [ ] Rerun assistant/worker tests and confirm a rejected/expired/deleted record cannot return in the next context pack.

## Task 7: Build the knowledge ledger and evidence map UI

**Files:**
- Create: `apps/web/src/features/projects/tabs/knowledge-tab.tsx`
- Create: `apps/web/src/features/projects/tabs/knowledge-tab.test.tsx`
- Modify: `apps/web/src/features/projects/project-detail-page.tsx`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/public/locales/{en,zh-CN}/projects.json`

- [ ] Write UI tests for record source opening, approve/reject controls based on role, deleted-record absence, and an empty state that explains the evidence-first workflow.
- [ ] Run the UI test and verify it fails before the tab exists.
- [ ] Add a project Knowledge tab with page/record list, proposal queue, evidence drawer, and simple relation map using the existing React Flow dependency. Every graph node must link to a record and source.
- [ ] Gate the optional 3D renderer behind a record-count threshold and `prefers-reduced-motion`; it must be a secondary inspection mode, not required navigation.
- [ ] Run the focused Vitest suite and `pnpm --filter @docpilot/web build`.

## Task 8: Add MemoryBench, operations documentation, review, and release evidence

**Files:**
- Create: `services/api/app/evaluation/memory_metrics.py`
- Create: `services/api/tests/evaluation/test_memory_metrics.py`
- Create: `benchmarks/bidbench/v1/demo-smart-community/memory-development.json`
- Modify: `docs/ops/deployment-and-runbook.md`
- Modify: `docs/development/configuration-and-secrets.md`
- Modify: `docs/quality/test-data-and-fixtures.md`
- Modify: `progress.txt`

- [ ] Write frozen-fixture tests for isolation, evidence provenance, delete/supersede correctness, degraded provider behavior, and context budget compliance.
- [ ] Run the evaluation test and verify it fails before the metric runner exists.
- [ ] Implement MemoryBench report generation with fixture fingerprint, retrieval profile, policy version, recall/provenance/deletion metrics, and explicit development-only labels.
- [ ] Document migration, key configuration, reindex/recompile rollback, audit queries, and what not to place in user/project memory. Do not put a secret value in docs or logs.
- [ ] Run all relevant API/worker/frontend tests, `git diff --check`, a focused independent review, and record remaining gaps in `docs/dev-log/` before any deployment.

## Self-review checklist

- [ ] PostgreSQL, not LangGraph Store, is business truth for every durable record.
- [ ] No tool or background job can create org-shared knowledge automatically.
- [ ] Every non-manual active record has evidence or an authorized human decision.
- [ ] Memory retrieval is authorization-first and profile-safe.
- [ ] Deletion, expiry, and supersede are observable in the next context pack.
- [ ] The graph visualization cannot show unauthorized or source-less relationships.
