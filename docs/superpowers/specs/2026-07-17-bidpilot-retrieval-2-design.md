# BidPilot Retrieval 2.0 Design

- Status: proposed for implementation
- Date: 2026-07-17
- Depends on: ADR 0001, ADR 0005, BidPilot product refoundation v2

## Goal

Replace the current vector-or-ILIKE fallback with a project-scoped evidence
retrieval system that is measurable, explainable, multilingual, and safe for
agent and workflow use.

Retrieval 2.0 returns evidence candidates, not model context. The caller still
decides how many validated candidates to send to a model, and every returned
candidate retains a stable source locator.

## Current defects

The current implementation has three independently maintained retrieval
paths: the API endpoint, the worker drafting helper, and the LangGraph
knowledge-retriever node. They rank differently and duplicate provider calls.
The API lets a browser submit a raw embedding, which makes model-space
provenance unverifiable. Worker failure can write all-zero vectors. The
database migration history removed the intended HNSW index, and there is no
schema-level proof that sparse indexing exists.

The existing parser records source document id, filename, heading path, table
information, and global chunk index in metadata_json, but no retrieval contract
checks whether those fields form a usable citation.

## Product contract

Every retrieval request is constructed server-side with:

- actor/org/project scope when called from the API;
- project scope inherited from an authorized ExecutionRun when called by a
  worker;
- query text and query kind: assistant question, requirement, section draft,
  review, or evidence lookup;
- a selected server-side retrieval profile;
- requested candidate and final-result counts;
- optional source-document and bundle filters.

A browser may supply query text, project id, and allowed UI filters. It cannot
supply an embedding, an org id, a retrieval profile, a provider secret, a
reranker selection, or an authorization decision.

The result contract is framework-neutral:

~~~python
@dataclass(frozen=True)
class RetrievalCandidate:
    chunk_id: str
    project_id: str
    source_document_id: str
    content: str
    locator: CitationLocator
    dense_rank: int | None
    sparse_rank: int | None
    fused_rank: int
    rerank_score: float | None
    final_score: float
    methods: tuple[str, ...]


@dataclass(frozen=True)
class RetrievalResult:
    candidates: tuple[RetrievalCandidate, ...]
    profile_id: str | None
    degraded_reasons: tuple[str, ...]
    trace: RetrievalTrace
~~~

The trace is internal/audit data. Runtime events and web UI receive only
localized candidate counts, safe source labels, and degradation summaries.
They never receive raw provider payloads, credentials, or hidden reasoning.

## Retrieval profile and indexing lifecycle

The first official profile is:

    openrouter:qwen/qwen3-embedding-8b:1536:bidpilot-lexical-v1

The profile id, embedding model, dimensions, normalization version, status,
and last successful indexing time are stored per KnowledgeChunk. Existing
chunks are marked legacy/stale until reindexed; they remain sparse-searchable
but are not silently mixed into a new dense vector space.

The embedding adapter exposes typed outcomes:

- configured and successful;
- not configured;
- transient provider failure;
- permanent provider rejection;
- returned dimension mismatch.

Only a configured successful outcome may persist an embedding. Batch failure
does not degrade to zero vectors. It marks the affected chunks retryable and
lets the bundle workflow report partial indexing.

## Sparse index design

New chunks receive search_text from a deterministic normalization function:

1. normalize Unicode and whitespace;
2. preserve Latin words, numbers, section numbers, standards, and identifiers;
3. append overlapping CJK n-grams for contiguous Chinese text;
4. preserve the original content for phrase and quote validation.

The migration installs pg_trgm, creates a GIN expression index over
to_tsvector('simple', search_text), a GIN trigram index over content, a B-tree
project_id index, and recreates the cosine HNSW index. The source migration
does not change the historical migration that accidentally dropped HNSW.

Sparse candidates are obtained in this order:

1. FTS matches ranked with ts_rank_cd;
2. exact phrase and trigram candidates for legacy data, CJK phrase searches,
   identifiers, and typo tolerance;
3. no broad "any chunk" fallback. Empty evidence is an explicit result.

## Dense candidate design

Queries are embedded server-side with the active retrieval profile. The query
is only compared to chunks having the same profile id and a non-null embedding.
For the current per-project workloads, dense search is exact inside the
authorized project scope. This avoids the recall trap of globally approximate
HNSW search followed by a tenant/project filter.

The HNSW index is retained and checked because it is needed when measurements
justify a future large-corpus execution mode. That mode is opt-in behind a
repository strategy and must pass the same retrieval evaluation suite before
becoming default.

## Fusion, rerank, and evidence checks

Dense and sparse candidate lists are deduplicated by chunk id and fused with
reciprocal-rank fusion:

    score(chunk) = sum(1 / (rrf_k + rank_for_each_retriever))

The initial rrf_k is 60 and is configuration, not a hidden prompt value.

Reranking is optional. When a server-side RERANK provider/model is configured,
the adapter reranks only the bounded fused candidate set. When it is absent or
fails, the pipeline returns the fused order with a degraded reason; it does not
make an unexpected paid call.

Each selected candidate must pass citation validation:

- its source_document_id matches the persisted chunk;
- it has a valid positive chunk_index;
- source metadata provides a text anchor, heading, table, or page marker;
- the anchor, when present, appears in the chunk content after normalization.

Validation yields verified, partial, or invalid. Invalid candidates are not
used as evidence. Partial candidates can be shown to a reviewer but cannot
alone satisfy a mandatory requirement. Contradiction detection remains a
later claim/evidence policy stage; Retrieval 2.0 surfaces mutually conflicting
source candidates without pretending to settle the contradiction.

## Integration boundaries

One retrieval service/repository contract is used by:

- the authenticated retrieval API;
- the worker drafting execution;
- the LangGraph knowledge-retriever node;
- future Agent, Requirement Ledger, Bid Wiki, and review tools.

LangGraph gets typed evidence results and writes its lifecycle through the
existing RuntimeRun event contract. It does not query database tables directly
to invent retrieval state.

## Observability and evaluation

Each retrieval trace records:

- request/run correlation ids;
- authorized project and selected filters;
- profile id and embedding outcome;
- candidate counts by dense, FTS, trigram, fusion, rerank, and validation;
- selected methods, degradation reasons, and latency buckets;
- result locator quality distribution.

Query text is not copied into public events. An audit/log sink may store a
redacted or hashed query according to retention policy.

BidBench retrieval evaluation adds:

- Recall at 1, 3, 5, and 10;
- MRR;
- locator validity rate;
- mandatory-requirement evidence recall;
- cross-project denial;
- no-provider and reranker-outage degraded-mode behavior;
- dense-only, sparse-only, fused, and reranked comparisons.

## Acceptance criteria

- API, drafting, and graph paths return the same retrieval contract for the
  same project/query/profile.
- A browser cannot inject a raw embedding or select another tenant's profile.
- All returned evidence is project-scoped and has a citation validation status.
- A Chinese query finds an indexed Chinese source through the sparse pipeline.
- A provider outage produces a visible degradation and never persists zeros.
- Existing chunks remain available through sparse retrieval until reindexing.
- The new PostgreSQL migration proves required extensions and indexes exist.
- Retrieval quality reports distinguish development fixtures from frozen
  commercial-quality evidence.

## Sources

- pgvector HNSW filtering and index guidance:
  https://github.com/pgvector/pgvector
- PostgreSQL full-text search controls and table indexes:
  https://www.postgresql.org/docs/current/textsearch-controls.html
  https://www.postgresql.org/docs/current/textsearch-tables.html
- OpenRouter embedding API:
  https://openrouter.ai/docs/api_reference/embeddings
