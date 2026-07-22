# ADR 0006: Quality Evaluation Release Gates

- Status: accepted
- Date: 2026-07-17
- Depends on: ADR 0001, ADR 0005, BidBench, RetrievalBench, MemoryBench, AssistantBench

## Context

BidPilot can now score requirement extraction, retrieval, governed memory, and
the governed Assistant's routing/policy boundary independently. A green unit
test or a single high benchmark score is not a release decision: it can be
generated from an old commit, a mutable development fixture, or an evaluation
that does not cover tenant isolation, provenance, or destructive-action safety.

The product's commercial promise is evidence-backed and governed bid execution.
Its release process must therefore reject a build that is only locally capable
of producing an attractive demo result.

## Decision

BidPilot uses a versioned, policy-based offline quality gate before a production
promotion. The gate consumes four already-captured reports:

1. `BidBench` for requirement, coverage, source association, and claim support;
2. `RetrievalBench` for ranking, locator validity, mandatory evidence, degraded
   behavior, and cross-project denial;
3. `MemoryBench` for authorized recall, isolation, provenance, private-memory
   ownership, and context budgets.
4. `AssistantBench` for intent routing, missing-input handling, required
   capability arguments, Runtime-policy parity, typed confirmation,
   project-scope safety, and unknown capability detection.

The policy is a reviewed JSON artifact. It explicitly names every threshold and
the only dataset roles allowed to support a release: `regression` and `hidden`.
`development` datasets can run the same gate in development mode, but their
output is never release-eligible.

Release mode requires an expected Git commit and every input report must declare
that exact commit. The generated gate artifact stores canonical SHA-256 hashes
of the policy and reports plus an input fingerprint. This gives reviewers a
stable audit handle without copying document bodies, prompts, model payloads, or
credentials into a second storage system.

The CLI is intentionally offline and provider-free. It is an optional but
required-for-promotion step of the release rehearsal because a release cannot
produce a quality verdict until reviewed regression or hidden artifacts exist.

## Consequences

Positive consequences:

- a development benchmark cannot become a false production green check;
- provenance, tenant isolation, and memory governance are release criteria,
  not dashboard-only metrics;
- Assistant routing and destructive-action policy regressions can block a
  release rather than being discovered only from a production conversation;
- metric thresholds become code-reviewed product policy instead of ad hoc CLI
  flags;
- reports from an old or unspecified code revision are rejected for release.

Costs and constraints:

- the team must curate regression and hidden fixtures before a production
  promotion can pass this gate;
- a policy threshold change needs the same review as a behavior change;
- report hashes provide audit traceability but are not cryptographic attestation
  against a privileged actor; CI artifact retention and repository access
  control remain required.

## Verification

The implementation is not complete unless:

- all four report kinds are mandatory;
- development roles or missing/mismatched commits fail release mode;
- safety metrics such as cross-project denial, provenance, isolation, private
  ownership, typed confirmation, project scope, and unknown capabilities are
  thresholded explicitly;
- the CLI writes a report with policy/report hashes and a stable input
  fingerprint;
- the release rehearsal can include the gate only when all report inputs and a
  target commit are provided.
