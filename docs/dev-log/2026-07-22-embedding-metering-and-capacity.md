# 2026-07-22 Embedding Metering and Capacity

## Outcome

Server-owned embedding requests now use the same organization-scoped token
ledger and hard platform ceiling as official LLM calls. The implementation
covers API evidence search, API governed-memory recall, bundle indexing,
memory indexing, LangGraph evidence retrieval, LangGraph memory retrieval, and
the legacy workflow fallback.

## Safety invariants

- Reserve a conservative UTF-8 upper bound before provider I/O in hosted
  environments.
- Settle exactly one usage record per HTTP response only when the provider
  reports `usage.total_tokens`; retain missing-usage outcomes as uncertain.
- Degrade query retrieval to lexical search when capacity is unavailable.
- Keep parsed source and old vectors when indexing cannot reserve capacity.
- Never include content, vectors, raw provider payloads, keys, or URLs in the
  usage ledger.
- Never batch memory text across organization, project, or private-owner
  boundaries.

## Verification

- API retrieval, memory, access, and usage regression: `78 passed`.
- Worker adapter, retrieval, memory, graph, and task regression: `61 passed`.
- Targeted Ruff checks passed for the touched API, Worker, and contract files.

## Still open

The ledger remains token-based. A reviewed provider price catalogue, invoice
reconciliation, production provider probes, and retained production release
artifacts are required before using it as a financial spend-control system.
