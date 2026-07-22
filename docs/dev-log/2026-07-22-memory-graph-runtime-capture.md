# Memory Graph Runtime Capture

## Goal

Make `MemoryGraphBench` capable of scoring an actual governed extraction run
without copying product identifiers, source text, evidence labels, locators,
provider payloads, or model reasoning into the benchmark artifact.

## Delivered

- Shared source-snapshot, proposal-fingerprint, and item-id helpers now prevent
  the API and Worker from independently reimplementing graph identity logic.
- `memory_graph_runtime_capture.py` accepts a private capture manifest and
  validates active shared source memory, graph proposal scope/type/expiry,
  source snapshot, successful `ExecutionRun`, successful `workflow_bridge`,
  review-decision scope/fingerprint, and exact benchmark evidence mapping.
- The generated `MemoryGraphEvaluationRun` uses only the frozen dataset case,
  organization, project, memory, and evidence identifiers.
- `capture_memory_graph_runtime_bench.py` requires an explicit
  `--confirm-redacted-graph-capture` acknowledgement and refuses output paths
  outside ignored `output/`.

## Safety Boundary

The private manifest contains durable database ids and stays outside Git and
normal build artifacts. The adapter cannot infer whether semantic entity names
are safe to export, so operators must only capture reviewed synthetic or
approved public source material. The CLI acknowledgement is an attestation,
not automatic privacy classification.

## Verification

- API graph metrics/capture/memory target suite: `36 passed`.
- Worker graph extraction suite: `2 passed`.
- API and contracts Ruff checks passed.
- Capture CLI `--help` completed without connecting to a provider or creating
  an artifact.

## Still Gated

- No `MemoryEntity` or `MemoryRelation` row is materialized by this work.
- No graph read model, graph prompt injection, Neo4j service, or 3D graph
  visualization is enabled.
- Gate B still requires a small human-reviewed synthetic/public corpus and
  retained controlled-capture evidence before any persistence-pilot review.
