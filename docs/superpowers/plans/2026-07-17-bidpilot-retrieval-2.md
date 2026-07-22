# BidPilot Retrieval 2.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Deliver one measured, project-scoped hybrid retrieval pipeline used consistently by API, drafting, and LangGraph workflows.

**Architecture:** Keep PostgreSQL plus pgvector. Introduce a stable retrieval profile, a deterministic lexical normalizer, dense and sparse candidate repositories, RRF fusion, an optional explicit reranker adapter, and citation validation. The API and Worker call the same contract; LangGraph remains an execution adapter rather than retrieval business truth.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, PostgreSQL 17, pgvector, pg_trgm, Celery, LangGraph, pytest.

**Reference design:** docs/superpowers/specs/2026-07-17-bidpilot-retrieval-2-design.md

---

## File map

- packages/contracts/retrieval.py: stable retrieval profiles, candidates, traces, and citation contracts.
- packages/contracts/models.py: typed chunk indexing fields.
- services/api/alembic/versions/<revision>_add_retrieval_2_indexes.py: additive schema, backfill markers, and required indexes.
- services/worker/app/retrieval/normalization.py: deterministic query/document lexical normalization.
- services/worker/app/adapters/embedding.py: typed provider outcomes and no-zero failure behavior.
- services/worker/app/retrieval/repository.py: PostgreSQL candidate queries and fusion-independent record reads.
- services/worker/app/retrieval/service.py: profile resolution, dense/sparse retrieval, RRF, rerank, locator validation, and trace creation.
- services/api/app/retrieval/service.py: authorization boundary and API mapping.
- services/worker/app/execution/{ingest.py,drafting.py}: profile-aware indexing and shared retrieval consumption.
- services/worker/app/graph/nodes/knowledge_retriever.py: maps shared results into graph state and runtime-safe history.
- services/api/app/evaluation/retrieval_metrics.py: retrieval metrics and baseline comparison.
- services/api/tests/retrieval/* and services/worker/tests/retrieval/*: unit, integration, migration, and regression tests.

## Task 1: Define the shared retrieval contract

**Files:**
- Create: packages/contracts/retrieval.py
- Modify: packages/contracts/__init__.py
- Test: services/api/tests/retrieval/test_contracts.py

- [ ] Write failing tests that reject empty profile ids, negative ranks, mismatched candidate project ids, and invalid citation locators.
- [ ] Define RetrievalProfile, EmbeddingOutcome, CitationLocator, RetrievalCandidate, RetrievalTrace, and RetrievalResult as framework-neutral Pydantic contracts.
- [ ] Export those contracts from packages/contracts/__init__.py.
- [ ] Run:

~~~powershell
uv run --directory services/api pytest tests/retrieval/test_contracts.py -q
~~~

Expected: all contract tests pass without importing FastAPI or LangGraph.

## Task 2: Add profile-aware chunk fields and PostgreSQL retrieval indexes

**Files:**
- Modify: packages/contracts/models.py
- Create: services/api/alembic/versions/<revision>_add_retrieval_2_indexes.py
- Test: services/api/tests/retrieval/test_retrieval_2_migration.py

- [ ] Write migration tests against a PostgreSQL database that assert:
  - pg_trgm is installed;
  - knowledge_chunk receives retrieval_text, embedding_profile, embedding_status,
    and embedding_updated_at;
  - the project B-tree, FTS GIN, trigram GIN, and cosine HNSW indexes exist;
  - legacy rows are marked stale rather than fabricated as current-profile data.
- [ ] Add nullable/index-safe model columns. Existing values must be preserved.
- [ ] Create an additive migration that installs pg_trgm, backfills retrieval_text
  from content, marks legacy embeddings stale, and recreates the HNSW index
  dropped by migration 27bbad823c47.
- [ ] Run:

~~~powershell
$env:DOCPILOT_DATABASE_URL='postgresql+psycopg://docpilot:docpilot@localhost:5433/docpilot_migration_test'
uv run --directory services/api alembic upgrade head
uv run --directory services/api pytest tests/retrieval/test_retrieval_2_migration.py -q
~~~

Expected: schema and every expected index are visible through pg_indexes.

## Task 3: Make embedding outcomes explicit and index documents safely

**Files:**
- Modify: services/worker/app/adapters/embedding.py
- Modify: services/worker/app/adapters/provider_env.py
- Modify: services/worker/app/execution/ingest.py
- Test: services/worker/tests/test_adapters.py
- Test: services/worker/tests/retrieval/test_indexing.py

- [ ] Write failing tests for OpenRouter Qwen 1536 output, a dimension mismatch,
  no provider configured, provider timeout, and batch partial failure.
- [ ] Replace all-zero fallback persistence with typed outcomes. Test-only stubs
  may remain explicit, but a production workflow must persist no embedding on
  a failed outcome.
- [ ] Derive one immutable profile id from provider, model, dimensions, and
  normalizer version. Store it with every successful embedding.
- [ ] Normalize retrieval_text during ingest and mark the individual chunk
  indexed only after both lexical persistence and successful vector persistence.
- [ ] Run:

~~~powershell
uv run --directory services/worker pytest tests/test_adapters.py tests/retrieval/test_indexing.py -q
~~~

Expected: failed provider calls leave embedding null and return a retryable state.

## Task 4: Implement sparse and dense candidate repositories

**Files:**
- Create: services/worker/app/retrieval/normalization.py
- Create: services/worker/app/retrieval/repository.py
- Test: services/worker/tests/retrieval/test_normalization.py
- Test: services/worker/tests/retrieval/test_repository_postgres.py

- [ ] Write failing tests for Latin tokens, CJK n-grams, punctuation/whitespace
  normalization, exact Chinese phrase candidates, and project scope isolation.
- [ ] Implement deterministic normalizers with no model call.
- [ ] Implement project-scoped dense exact search that only compares matching
  profiles. Implement FTS candidates ranked by ts_rank_cd and pg_trgm/phrase
  candidates for legacy and CJK cases.
- [ ] Do not add a broad any-chunk fallback. An empty result is a valid result.
- [ ] Run:

~~~powershell
uv run --directory services/worker pytest tests/retrieval/test_normalization.py tests/retrieval/test_repository_postgres.py -q
~~~

Expected: a Chinese query returns its own project source and never a foreign one.

## Task 5: Add fusion, rerank, locator validation, and observability

**Files:**
- Create: services/worker/app/retrieval/service.py
- Create: services/worker/app/retrieval/reranker.py
- Test: services/worker/tests/retrieval/test_service.py
- Test: services/worker/tests/retrieval/test_reranker.py

- [ ] Write failing tests for deterministic RRF, duplicate merging, reranker
  disabled, reranker failure, valid/partial/invalid locators, and no-vector
  degraded results.
- [ ] Implement RRF with documented rrf_k=60 and stable chunk-id tie breaking.
- [ ] Add an explicit optional HTTP reranker adapter. It must make no outbound
  call unless its URL, API key, and model are all configured.
- [ ] Validate source document id, chunk index, metadata locator, and anchor
  before returning final evidence.
- [ ] Record candidate counts, modes, profile, safe error category, and
  latency in RetrievalTrace.
- [ ] Run:

~~~powershell
uv run --directory services/worker pytest tests/retrieval/test_service.py tests/retrieval/test_reranker.py -q
~~~

Expected: fused results remain deterministic during configured-reranker outage.

## Task 6: Replace duplicated API and Worker retrieval paths

**Files:**
- Modify: services/api/app/retrieval/{schemas.py,repository.py,service.py,router.py}
- Modify: services/worker/app/execution/drafting.py
- Modify: services/worker/app/graph/nodes/knowledge_retriever.py
- Modify: services/worker/app/graph/state.py
- Test: services/api/tests/retrieval/test_search.py
- Test: services/worker/tests/test_graph_integration.py
- Test: services/worker/tests/test_section_drafter.py

- [ ] Write integration tests proving API authorization happens before retrieval,
  client-supplied embeddings are rejected, and API/drafting/graph use the same
  ordering for the same fixture.
- [ ] Map public API responses to safe result fields; return an explicit
  retrieval degradation rather than an HTTP 200 with fabricated confidence.
- [ ] Replace the drafting helper and graph node direct SQL with shared service
  calls. Retain only a small graph-state mapping layer.
- [ ] Emit only user-facing retrieval summaries through runtime events.
- [ ] Run:

~~~powershell
uv run --directory services/api pytest tests/retrieval -q
uv run --directory services/worker pytest tests/test_graph_integration.py tests/test_section_drafter.py -q
~~~

Expected: no production path imports KnowledgeChunk directly for ranking outside
the shared retrieval repository.

## Task 7: Add BidBench retrieval evaluation and release evidence

**Files:**
- Create: services/api/app/evaluation/retrieval_metrics.py
- Create: services/api/tests/evaluation/test_retrieval_metrics.py
- Create: sample-data/bidbench/retrieval-development/...
- Modify: docs/quality/test-data-and-fixtures.md
- Modify: docs/dev-log/2026-07-17-retrieval-2-foundation.md
- Modify: progress.txt

- [ ] Define fixture labels with query, authorized project, relevant chunk ids,
  expected source locator, and mandatory-evidence flag.
- [ ] Add Recall at k, MRR, locator-validity, evidence-recall, cross-project
  denial, and degraded-mode metrics.
- [ ] Run dense-only, sparse-only, fused, and reranked development reports
  against the same frozen input fingerprint.
- [ ] Record provider/model/profile, candidate limits, code revision, cost, and
  latency for each report.
- [ ] Run:

~~~powershell
uv run --directory services/api pytest tests/evaluation/test_retrieval_metrics.py -q
~~~

Expected: a report cannot compare methods from different source fixtures or
profiles without calling the comparison invalid.

## Task 8: Review, verification, and rollout

**Files:**
- Modify: docs/ops/deployment-and-runbook.md
- Modify: docs/development/local-environment-baseline.md
- Test: relevant API, Worker, and web suites

- [ ] Add a reindex runbook: profile change, stale chunk count, background
  enqueue, completion evidence, rollback, and no-mixed-space guard.
- [ ] Add configuration documentation for official embeddings and optional
  reranker without exposing any value.
- [ ] Run migration smoke tests, full API suite, full Worker suite, frontend
  tests, and web build.
- [ ] Request an independent code review focused on cross-project isolation,
  zero-vector contamination, index migration safety, provider cost boundaries,
  and citation validation.
- [ ] Record known gaps and proof in the dev log before any deployment.

## Self-review checklist

- [ ] Every Retrieval 2.0 design acceptance criterion maps to a task above.
- [ ] No task permits a browser to submit raw vectors or provider credentials.
- [ ] No task relies on an unmeasured globally filtered ANN result.
- [ ] No task changes the historical migration that dropped HNSW.
- [ ] All paid provider calls are opt-in/configured and have failure tests.
