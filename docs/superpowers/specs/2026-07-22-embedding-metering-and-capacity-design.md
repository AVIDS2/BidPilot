# Embedding Metering and Capacity Design

## Status

Implemented and locally verified on 2026-07-22. Currency reconciliation and
real-provider release evidence remain out of scope.

## Problem

BidPilot already records provider-reported LLM usage and protects
platform-funded LLM calls with a per-workspace token ceiling. Embedding calls
are also platform-funded: bundle indexing, governed-memory indexing, evidence
search, and memory recall all use the server-owned embedding provider. The
adapters parse OpenAI-compatible `usage.total_tokens`, but those values are not
currently persisted or reserved. A document-indexing job count is a useful
product quota, not a reliable provider-cost ledger.

## Decision

Treat every platform-owned embedding HTTP request as a model invocation in the
existing `ModelUsageReservation` and `ModelUsageRecord` ledger.

1. Before dispatch, reserve a conservative upper bound equal to UTF-8 byte
   length plus a small per-input allowance. This deliberately over-reserves;
   it is a safe upper bound rather than a tokenizer claim.
2. A successful provider response settles to its single, provider-reported
   `usage.total_tokens`, recorded once per HTTP request rather than once per
   returned vector.
3. A response without usage, timeout, or transport ambiguity keeps its
   reservation `uncertain` until normal expiry. A known non-billable
   configuration or permanent provider rejection releases it.
4. The effective cap remains the strictest of the platform
   `DOCPILOT_OFFICIAL_MONTHLY_TOKEN_CEILING` and any lower organization cap.
   BYOK is intentionally not used for embeddings in this version.
5. Query embedding that cannot reserve capacity degrades to lexical retrieval;
   it must not bypass the ledger or make the whole read path fail.
6. Bundle and memory indexing that cannot reserve capacity retain parsed text
   and existing vectors, mark the embedding outcome as budget-limited, and can
   be retried after capacity is available.

## Coverage

- bundle chunk indexing and explicit reindex;
- governed-memory record indexing;
- API evidence-search query embedding;
- API assistant-memory context query embedding;
- Worker workflow evidence and memory-context query embedding.

## Security and privacy

- The ledger stores only organization/project/runtime correlation, provider
  family/model, workload, and numeric usage. It never stores query text,
  vectors, response bodies, API keys, or provider payloads.
- Background indexing may have no single user actor. Its reservation and record
  may therefore have a null user reference while remaining organization and
  project scoped; the initiating `UsageEvent` remains the human-action audit
  record.
- A provider response that omits usage is not silently treated as free.

## OpenRouter compatibility

OpenRouter documents `usage.prompt_tokens` and `usage.total_tokens` for its
Embeddings endpoint, including zeroed fields for cache hits. The adapter treats
the presence of the usage field separately from its numeric value so a valid
zero-cost cache hit can settle to zero while an omitted usage field remains
uncertain. Reference: https://openrouter.ai/docs/guides/features/response-caching

## Non-goals

- currency reconciliation, invoice matching, and a mutable provider price
  catalogue;
- browser-submitted vectors, embedding API keys, or client-provided token
  counts;
- user-selectable BYOK embeddings;
- a best-effort token estimator presented as provider-reported usage.

## Acceptance criteria

- a batch response with `usage.total_tokens=N` writes one `ModelUsageRecord`
  with `input_tokens=total_tokens=N`, independent of vector count;
- all platform embedding dispatches reserve capacity before I/O in hosted
  environments;
- concurrent reservations cannot exceed the organization ceiling;
- a missing usage field keeps capacity reserved, while a known unbilled failure
  releases it;
- an exhausted query budget returns a safe lexical/degraded retrieval result;
- no raw text, vectors, provider payloads, or credentials appear in model usage
  records, runtime events, or logs;
- unit and migration-backed tests cover the new paths.

## Implementation evidence

- API evidence search and governed-memory query paths use a dedicated metered
  embedding boundary that owns its own database transaction, preventing a
  usage reservation from committing unrelated caller state.
- Bundle indexing and governed-memory indexing reserve before dispatch and
  settle provider usage in the same transaction that records the refreshed
  retrieval state. A budget-limited refresh retains any existing vector.
- Memory indexing groups each provider batch by organization, project, and
  private-memory owner, so one third-party embedding request never contains
  content from different organizations.
- Worker workflow evidence and memory-context retrieval require a trusted
  runtime principal before issuing a provider embedding request; otherwise the
  existing lexical retrieval path remains available.
- Local regression evidence: API retrieval/memory/usage coverage `78 passed`;
  Worker retrieval/memory/task coverage `61 passed` on the dedicated test
  database. These tests are implementation evidence, not a real-provider or
  production-release attestation.
