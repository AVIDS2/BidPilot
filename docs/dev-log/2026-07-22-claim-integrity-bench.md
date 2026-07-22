# Claim Integrity Bench

## Goal

Measure whether a human-accepted response claim preserves the full reviewed
Requirement -> Evidence -> Claim contract, rather than merely citing any known
piece of evidence.

## Delivered

- BidBench v2.1 adds `claim_trace_integrity_rate` and aggregate counters for
  unknown requirement references, missing/unknown evidence references, and
  unsupported requirement/evidence pairs.
- The evaluator maps candidate requirement ids through the existing
  deterministic requirement matcher, then requires every candidate
  requirement/evidence cross-product pair to be present in the frozen dataset
  support matrix. This matches the current Claim Integrity v1 persistence
  contract.
- Existing `unsupported_claim_rate` remains unchanged for historic report
  comparability. New metrics and counts have compatible defaults, so old
  report shapes still parse.
- A reviewed policy can now opt into `min_claim_trace_integrity_rate` through
  the existing quality gate or `run_bidbench.py`. A `null` result is an
  explicit threshold failure when the policy asks for the metric.

## Verification

- BidBench, current-pipeline adapter, and quality-gate coverage: `46 passed`.
- New unit cases prove that an unknown requirement reference and a known
  evidence id attached to the wrong requirement fail structural trace
  integrity.
- `run_bidbench.py --help` exposes the new threshold without connecting to a
  provider.

## Still Gated

- This is a structural benchmark. It does not establish semantic entailment or
  factual truth of a claim.
- Development data cannot set the production threshold. A reviewed regression
  or hidden capture with retained provenance must establish a baseline first.
- No product export behavior changes until a separate version-level export
  policy, legacy strategy, remediation flow, and controlled evidence review
  are approved.
