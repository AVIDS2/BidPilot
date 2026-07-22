# ADR 0005: Retrieval Profile and Hybrid Search

- Status: accepted
- Date: 2026-07-17
- Depends on: ADR 0001, the BidPilot product refoundation design

## Context

BidPilot currently stores document chunks in PostgreSQL and embeddings in
knowledge_chunk.embedding VECTOR(1536). Retrieval is effectively either
vector search or ILIKE fallback. This has four production problems:

1. a changed embedding model can silently mix incompatible vector spaces;
2. an embedding provider failure is currently converted into an all-zero
   vector and persisted as if indexing succeeded;
3. PostgreSQL simple full-text search does not tokenize Chinese phrases in a
   useful way, so a Chinese query can miss an otherwise exact Chinese source;
4. an old migration accidentally dropped the HNSW index during a later
   subscription migration, so having an index definition in source did not
   prove an index existed in a migrated database.

The platform already uses PostgreSQL, pgvector, Redis, and a worker. Adding a
second vector database would duplicate tenancy, backup, audit, access-control,
and operational concerns before the current database is close to its limits.

## Decision

BidPilot keeps PostgreSQL plus pgvector as the only retrieval storage engine
for the BidPilot scenario. Retrieval 2.0 uses one bounded, project-scoped
hybrid pipeline:

1. server-side scope and project authorization;
2. query normalization;
3. dense candidates from pgvector;
4. sparse candidates from PostgreSQL full-text search and pg_trgm;
5. reciprocal-rank fusion;
6. optional configured reranking;
7. citation-locator validation and evidence sufficiency classification.

### Retrieval profiles

Every non-null embedding belongs to an immutable retrieval profile:

    provider:model:dimensions:normalizer-version

The initial official profile is OpenRouter, Qwen3 Embedding 8B, 1536 output
dimensions, and the current BidPilot query/document normalization version.
Qwen3 supports reduced output dimensions and OpenRouter exposes the optional
dimensions request parameter; retaining 1536 dimensions preserves the
existing VECTOR(1536) physical schema.

Documents and queries may only be compared when their profile identifiers
match. A changed profile creates a reindex requirement; it must not silently
mix old and new embeddings.

Platform-owned retrieval configuration is server-side. BYOK may power a user's
chat or drafting model, but it cannot silently replace an organization's
retrieval profile. A future organization-level embedding-profile setting must
have explicit approval, reindexing, cost policy, and audit behavior.

### Sparse retrieval and Chinese content

PostgreSQL FTS with the simple configuration is retained for English and
structured tokens. New chunks also store a normalized lexical representation
that adds CJK n-grams. This gives FTS usable Chinese candidates without
requiring an unmaintained server-side tokenizer extension. pg_trgm indexes the
raw content for exact phrase, typo, and legacy-data fallback.

### Vector indexes

The product keeps a cosine HNSW index for the stable 1536-dimensional column,
but does not rely on a global approximate index to prove correct results after
a narrow project filter. At current project sizes, dense retrieval is exact
inside the authorized project scope. A future large-corpus mode may use a
verified HNSW candidate scan only with measured recall and a compatible
pgvector configuration.

The Retrieval 2.0 migration recreates the missing HNSW index, adds the
project and lexical indexes, and has an index-existence test against a real
PostgreSQL database. Production rollout must create large indexes
concurrently or during a maintenance window.

### Reranking and failure behavior

RRF is deterministic and always available. Remote reranking is an adapter
behind explicit server configuration and is off by default; an absent or
unavailable reranker records a visible degraded mode and returns fused
results. It never silently invokes a paid provider.

An unavailable embedding provider produces an explicit indexing or retrieval
degradation. It does not write a zero vector, claim success, or contaminate
the vector index.

## Consequences

Positive consequences:

- one audited and tenant-safe retrieval store;
- reproducible query/profile provenance for every answer and workflow run;
- useful sparse candidate retrieval for Chinese and English;
- deterministic behavior when a reranker is not configured;
- a measurable path from dense-only retrieval to hybrid retrieval.

Costs and constraints:

- changing the official embedding profile requires a controlled reindex;
- FTS plus trigram indexes increase storage and ingest write cost;
- exact per-project vector search is deliberately favored over approximate
  global index speed until corpus measurements justify a different mode;
- retrieved results must carry structured provenance, not only text snippets.

## Verification

Retrieval 2.0 is not complete until:

- every persisted embedding has a profile or is explicitly marked stale;
- provider failures produce no persisted zero vectors;
- the migrated PostgreSQL schema contains vector, project, FTS, and trigram
  indexes;
- cross-project candidates cannot appear in API or worker retrieval;
- BidBench retrieval fixtures report recall at k, MRR, locator validity, and
  degraded-mode behavior for dense-only, sparse-only, fused, and reranked
  modes.
