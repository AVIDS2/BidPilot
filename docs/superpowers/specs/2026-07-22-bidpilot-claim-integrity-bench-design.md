# BidPilot Claim Integrity Bench

## Status

- Date: 2026-07-22
- Status: approved implementation slice
- Depends on: BidBench v2, Requirement Ledger, Claim Integrity v1, and the
  existing release-quality gate

## Problem

`BidBench.unsupported_claim_rate` currently answers one narrow question: does
an accepted factual claim cite at least one known benchmark evidence id? It can
therefore report a claim as grounded when that evidence belongs to a different
requirement. That is insufficient for BidPilot's actual control promise:

```text
Requirement -> Evidence -> Claim -> Deliverable version
```

The benchmark must evaluate the structural integrity of this trace separately
from semantic truthfulness. A deterministic offline evaluator cannot prove
that a sentence is factually true; it can prove that the evaluated system did
or did not preserve the reviewed requirement/evidence contract.

## Decision

Add a backward-compatible `claim_trace_integrity_rate` to BidBench. It applies
only to `accepted` claims, which the current-pipeline adapter derives from
human-verified or approved Requirement Ledger claims.

For each accepted claim, the evaluator requires all of the following:

1. it has one or more candidate requirement ids;
2. every candidate requirement id maps through the deterministic requirement
   matcher to a ground-truth requirement;
3. it has one or more evidence ids and every id is present in the benchmark
   evidence registry; and
4. every candidate requirement/evidence cross-product pair is an explicitly
   supported pair in the frozen dataset.

The final rule intentionally matches Claim Integrity v1 persistence, which
creates a `RequirementEvidenceLink` for every validated candidate
requirement/evidence pair. A future product contract that permits a sparse
many-to-many mapping must introduce an explicit pair-level candidate field and
a new evaluator formula; it must not silently weaken this rule.

## Metric Semantics

- `unsupported_claim_rate` remains its existing coarse factual-claim metric
  for historic report comparability.
- `claim_trace_integrity_rate` is the proportion of accepted claims whose
  full requirement/evidence trace is structurally valid. It is `null` when no
  accepted claims exist.
- The report also emits redacted aggregate counts for claims with unknown
  requirement references, missing/unknown evidence references, and unsupported
  requirement/evidence pairs. It never emits candidate claim text, customer
  IDs, source bodies, or evidence quotes.
- A new optional `min_claim_trace_integrity_rate` threshold can be enabled in
  a reviewed quality-gate policy. When configured, an unavailable metric fails
  the threshold rather than becoming a false green result.

## Non-Goals

- no model call, semantic NLI judge, or self-grading prompt;
- no automatic approval of a Claim;
- no production export blocker in this slice;
- no conversion of development fixtures into a release threshold;
- no retention of customer claim text in benchmark reports.

## Rollout

1. Use the offline Claim Integrity runtime-capture adapter against reviewed
   synthetic or public snapshots instead of hand-authoring current-pipeline
   candidates.
2. Collect a controlled regression/hidden capture with two-person review and
   release provenance.
3. Propose the threshold from observed baselines, then review it as policy.
4. Only after that evidence, design a separate version-level export gate with
   a legacy-version migration and user remediation path.
