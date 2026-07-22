# Claim Integrity v1

## Goal

Turn the product's declared bid trace from a set of independent tables into a
reviewable workflow invariant:

```text
Requirement -> Evidence -> Claim -> Deliverable version
```

## Delivered

- The existing LangGraph quality-review call now returns an optional bounded
  claim-attribution list alongside its normal review result. This is a
  sequential handoff, not a new supervisor, fan-out, or extra paid model call.
- The model receives only request-local `R1` requirement and `E1` evidence
  aliases. The Worker accepts a candidate only when its text is verbatim in
  the final draft and every alias is in the current project/section/evidence
  scope.
- `persist_result` creates draft AI claims and all three trace links in the
  same transaction as the `SectionVersion` and its evidence. A replay reuses
  the committed version rather than duplicating claims or links.
- Execution and runtime data retain aggregate claim counts and an integrity
  status only; claim text, evidence quotes, alias maps, raw model JSON, and
  reasoning are not copied into those event surfaces.
- The Requirement Ledger now exposes the real review order: verify supporting
  evidence first, then verify a factual AI-proposed claim. Backend capability
  checks remain authoritative for both actions.
- A shared Claim cannot be globally verified from one requirement alone. The
  verifier now requires verified support pairs for every Claim-linked
  requirement and recomputes all affected readiness profiles atomically.
- The Assistant now has a read-only Claim Review Queue capability. It reports
  only the count of AI-created draft claims, how many have all required
  verified support pairs, and how many remain blocked by evidence. It cannot
  verify claims, alter evidence, or transmit draft claim text through SSE,
  audit events, or public Runtime results.
- The production LangGraph Operator and legacy ReAct compatibility route share
  the same queue capability through the Runtime control plane. A deleted or
  stale BYOK provider selection falls back to the governed official provider
  without decrypting or substituting a user secret.
- Worker tests now clear inherited official chat-provider credentials and use
  the local deterministic stub unless a test explicitly injects a fake
  credential and transport mock. Tests can no longer accidentally call a
  billable provider from a developer machine.

## Verification

- Claim, graph-state, governed-node, drafting, and persistence scope suite:
  `27 passed`.
- Existing Requirement Ledger API and trace-model regression: `14 passed`.
- Cross-requirement Claim verification regression: `15 passed` after the
  shared-Claim consistency check.
- Worker graph, task, adapter, governed-node, and Claim regression: `41
  passed`.
- Full Worker suite after provider-environment isolation: `123 passed`.
- Requirement Ledger component suite: `8 passed`.
- Web TypeScript compile and production Vite build passed.
- Assistant, Requirement Ledger, Operator, and policy regression: `58 passed`
  on a freshly migrated dedicated local `_test` database.

## Still Gated

- A Claim remains a human-review proposal. No model output is automatically
  factual, verified, or coverage-closing.
- Export does not fail closed on unverified claims in v1. Historic versions do
  not have comparable integrity data, so an export gate needs an explicit
  migration and remediation design.
- BidBench must gain controlled unsupported-claim measurements before setting
  a claim-integrity release threshold or changing export policy.
- There is no retroactive extraction over existing customer drafts and no
  automatic memory/knowledge-graph write-back from claims.
