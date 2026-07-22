# BidPilot Claim Integrity v1

## Status

- Date: 2026-07-22
- Status: approved implementation slice
- Depends on: Requirement Ledger, Evidence records, governed workflow model
  usage, human review, and the Unified Runtime

## Problem

BidPilot already persists `Claim`, `RequirementClaimLink`, and
`ClaimEvidenceLink` records, but those links are currently created only by a
manual Requirement Ledger action. The drafting workflow writes a section and
its retrieved evidence without creating a durable bridge from the generated
assertions to the requirements and evidence they are meant to support.

That leaves the intended trace incomplete:

```text
Requirement -> Evidence -> Claim -> Deliverable version
```

The product must not treat an LLM sentence as a verified fact merely because it
was generated beside relevant evidence.

## Decision

Extend the existing sequential LangGraph handoff, rather than adding a new
supervisor or a second paid model call:

```text
section drafter
    -> quality reviewer + claim attribution
    -> human approval
    -> transactional persistence
```

The quality reviewer already receives the draft, requirements, and a governed
model reservation. It will return an optional bounded list of **claim
candidates** as part of its structured response. Those candidates are not
facts and are not trusted until the Worker validates every reference and writes
them as `draft` claims for human verification.

## Candidate Contract

The model sees local aliases only:

```json
{
  "claims": [
    {
      "text": "A verbatim factual or inferential statement from the draft.",
      "claim_type": "factual",
      "requirement_refs": ["R1"],
      "evidence_refs": ["E1"]
    }
  ]
}
```

`R1` and `E1` are request-local aliases created by the Worker. Durable
requirement IDs, evidence IDs, document IDs, provider payloads, and model
reasoning never appear in the model prompt, workflow history, runtime events,
or user-facing tool output.

The Worker accepts a candidate only when all of the following hold:

1. the text is a bounded, normalized substring of the final draft;
2. `claim_type` is `factual` or `inference`;
3. every requirement alias maps to an authorized requirement in the current
   project and section scope;
4. every evidence alias maps to a retrieved evidence chunk for this run; and
5. the candidate has at least one requirement and one evidence reference.

Invalid candidates are discarded and counted as a safe integrity degradation.
They do not become claims, evidence links, or an approval bypass.

## Persistence and Lifecycle

`persist_result` continues to create the `SectionVersion` and `Evidence`
records in one transaction. It then maps accepted candidate chunk aliases to
the just-created `Evidence` rows and creates:

- a `Claim` with `status=draft`, `created_by_actor=ai`, current
  `section_version_id`, and current `generation_run_id`;
- one unverified `RequirementEvidenceLink` plus one `RequirementClaimLink` per
  validated requirement; and
- one unverified `ClaimEvidenceLink` per validated persisted evidence row.

The existing Requirement Ledger verification command remains the sole path to
mark a claim and its evidence links `verified`. Replays must not duplicate
claims for the same run/version/normalized text/reference tuple.

When one Claim is linked to multiple requirements, verification is global to
that Claim: every linked requirement must have verified support for every
linked Claim evidence row before the Claim can become `verified`. The command
then recomputes every linked requirement profile in the same transaction. A
single requirement's evidence must never make another linked requirement look
covered.

The `ExecutionRun` output receives aggregate counts and a safe integrity state
only. It does not store claim text, evidence quotes, aliases, raw response JSON,
or provider diagnostics.

## Review and Export Policy

This v1 slice exposes traceability and reviewer work; it does not introduce an
instant global export blocker. Existing historical section versions lack claim
assessment data, and unvalidated automatic export blocking would silently
break established projects.

The next gate, after controlled BidBench evaluation and user-review evidence,
will add a version-level claim-integrity status and make exports fail closed for
new governed versions with unverified factual claims. That separate change must
include migration, user-facing remediation, policy controls, and an explicit
legacy strategy.

## Non-Goals

- no automatic factual verification;
- no model-generated claim is auto-approved;
- no hidden chain-of-thought or raw model JSON retention;
- no retroactive claim extraction over existing customer drafts;
- no extra model call, supervisor, or multi-agent fan-out;
- no graph materialization or automatic knowledge write-back.

## Evaluation and Acceptance

The implementation is complete only when:

1. a valid reviewer response creates project-scoped draft claims linked to the
   generated section version and persisted evidence;
2. invented draft text, unknown aliases, cross-section requirements, and
   unobserved evidence aliases create no claim;
3. a retry or replay cannot duplicate the same durable claim links;
4. the existing human verifier can promote only claims whose supporting
   requirement evidence is already verified for every linked requirement;
5. worker/provider usage remains one quality-review call, not an added call;
   and
6. Worker and API regression tests cover the boundary.

BidBench v2.1 now adds the separate structural
`claim_trace_integrity_rate` described in
`2026-07-22-bidpilot-claim-integrity-bench-design.md`. A reviewed threshold
and a version-level export-gate experiment remain future work. Neither metric
is evidence that a model's claims are semantically correct.

An offline Claim Integrity runtime-capture adapter now provides the only
approved bridge from a reviewed real workflow run to a BidBench candidate. It
validates the execution/runtime provenance and exact private mapping coverage,
then emits only frozen benchmark identifiers and opaque candidate identifiers.
It does not export project data, Claim text, evidence text, locators, durable
database IDs, or model payloads.
