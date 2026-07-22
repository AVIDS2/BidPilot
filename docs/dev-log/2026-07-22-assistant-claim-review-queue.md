# Assistant Claim Review Queue

## Problem

Claim Integrity v1 created durable draft Claims, but the Agent could not guide
a reviewer toward the human verification step. Letting the Agent verify claims
would violate the product's evidence and approval boundary.

## Decision

Add one project-scoped, read-only Runtime capability:

```text
list_claim_review_queue
```

It returns only aggregate progress for AI-created draft claims:

- claims waiting for a human reviewer;
- claims whose full requirement/evidence support matrix is already verified;
- claims blocked by missing or unverified support.

The domain query can identify queue items for an authenticated future workbench
surface, but the Assistant tool, Runtime action, public event payload, and SSE
transport intentionally expose no Claim text, evidence quote, requirement
text, internal Claim identifier, or model output.

## Invariant

For a factual Claim linked to requirements `R` and evidence `E`, the queue
marks it ready only when every pair in `R x E` has a verified `supports`
RequirementEvidenceLink. This mirrors the actual Claim verification command;
a shared Claim cannot appear ready from evidence attached to only one
requirement.

## Runtime Boundary

The production LangGraph Operator plans against the Runtime capability
registry. Runtime executes the capability through the existing typed Assistant
adapter, applies `project.read`, audits it as a read, and publishes only the
public count summary. The legacy ReAct fallback registers the same tool so
engine choice cannot silently remove a capability.

## Provider Boundary

An explicit provider configuration is a billing and authorization choice, not
a cosmetic UI preference. If the selected BYOK configuration is deleted or no
longer owned by the caller, the Assistant returns a safe `404` and does not
fall back to the platform-funded provider. The official provider is used only
when the request does not select a provider configuration at all.

## Verification

- Assistant SSE regression proves a draft Claim body never appears in the
  response while one ready and one blocked Claim yield the correct counts.
- Operator graph regression proves the production Runtime boundary can execute
  the capability and publish only its public summary.
- Assistant/Requirement Ledger/Operator/policy regression: `58 passed`.
- Targeted Ruff checks passed.
