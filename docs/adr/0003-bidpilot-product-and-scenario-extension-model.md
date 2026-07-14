# ADR 0003: BidPilot Product Identity and Scenario Extension Model

- Status: Accepted
- Date: 2026-07-14
- Supersedes: the "no scenario-specific DB tables" rule in ADR 0002

## Context

ADR 0002 correctly protected the shared control plane from early duplication, but its rule that every new scenario must require only registry metadata is too restrictive for a mature vertical product.

Bid response has durable domain concepts that do not belong in a generic document model, including scoring weights, mandatory submission conditions, bid-specific risk, requirement closure, and response readiness.

At the same time, exposing DocPilot as a multi-scenario product weakens the current commercial position. The customer-facing product is BidPilot.

## Decision

1. The external product name and user experience are `BidPilot`.
2. Internal reusable infrastructure may remain scenario-neutral where that reduces duplication.
3. Shared control-plane models contain only concepts that are genuinely reusable, such as projects, source provenance, assignments, evidence, claims, reviews, approvals, executions, and audit.
4. Bid-specific durable fields live in explicit BidPilot extension tables and services, not in untyped JSON blobs and not in unrelated shared columns.
5. Scenario packages continue to provide templates, extraction configuration, prompts, and export conventions.
6. Adding a future scenario may require a new extension module and migration. It must not require forking the shared control plane.

## Initial Boundary

Shared domain:

- Project, Bundle, SourceDocument, ParsedAsset, KnowledgeChunk
- RequirementItem source provenance and human assignment
- Evidence, Claim, requirement/evidence/claim trace links
- Deliverable, SectionVersion, Review, Approval, ExecutionRun
- Audit, usage, organization, team, and permissions

BidPilot extension:

- mandatory/scored/qualification/commercial/technical classification
- score weight and bid-specific risk
- coverage and evidence-readiness policy
- bid deadlines and submission constraints
- Bid Readiness Pack and response-completeness calculations

## Consequences

- The product can become deeply vertical without contaminating reusable infrastructure.
- ADR 0002 remains valid for registry-driven configuration, but not for the prohibition on extension tables.
- New scenario work remains out of scope until BidPilot passes its completion gates.
- Schema reviews must justify whether a field belongs in the shared domain or the BidPilot extension.

