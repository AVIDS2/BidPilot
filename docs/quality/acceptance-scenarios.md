# Acceptance Scenarios

## Goal

Define the canonical scenarios that must pass before DocPilot is considered operationally credible.

These scenarios are intentionally end-to-end and closer to production behavior than unit or integration tests alone.

## Working rule

Each phase should map its exit criteria to one or more scenarios here.

## Shared fixture policy

- keep one small public-safe document bundle for repeatable local validation
- keep one medium realistic bundle for staging-grade checks
- do not rely on private customer material for baseline acceptance

## Scenario AC-01: Local stack bootstrap

Purpose:

- prove the base engineering stack is usable by any future implementer

Steps:

1. start infrastructure and application services
2. apply migrations
3. hit health endpoints
4. create one project

Expected outcomes:

- all services boot cleanly
- health checks succeed
- project creation succeeds

## Scenario AC-02: Bid bundle to evidence-backed draft

Purpose:

- prove the core BidPilot loop works end to end

Steps:

1. create a project
2. upload one bundle with multiple source documents
3. run parse and indexing
4. extract requirements
5. trigger one section draft

Expected outcomes:

- source documents are registered and parsed
- requirement items exist
- one section draft is created
- the draft includes evidence links or an explicit missing-evidence marker

## Scenario AC-03: Review, reject, rerun, approve

Purpose:

- prove human review is part of the real workflow

Steps:

1. open a review thread on a drafted section
2. reject the draft with a reason
3. rerun the section
4. approve the new version

Expected outcomes:

- review history remains durable
- version history shows both attempts
- approval state is visible in system records

## Scenario AC-04: Export from approved content

Purpose:

- prove the system produces a real deliverable, not only intermediate AI artifacts

Steps:

1. ensure required sections are approved
2. trigger export
3. retrieve the exported artifact and audit history

Expected outcomes:

- export completes successfully
- export references approved section versions
- artifact metadata and audit events are queryable

## Scenario AC-05: Failure recovery and traceability

Purpose:

- prove operator visibility and recovery behavior

Steps:

1. simulate a provider or parser failure
2. inspect run status, logs, and traces
3. retry or rerun the affected task

Expected outcomes:

- failure is visible through durable run state
- raw provider failure is normalized
- retry preserves traceability

## Scenario AC-06: Backup and restore drill

Purpose:

- prove production claims are backed by recovery practice

Steps:

1. create a representative staging project
2. take database backup and verify object availability
3. restore into a clean staging environment
4. validate project visibility and export history

Expected outcomes:

- restored system is usable
- core project and deliverable records survive
- recovery procedure is documented and repeatable

## Scenario AC-07: Public historical procurement rehearsal

Purpose:

- validate the core governed workflow against a medium public procurement
  corpus without introducing customer material into the repository

Steps:

1. download the source-manifest-pinned public materials to ignored local storage
2. verify file hash and PDF signature before upload
3. create an isolated project and upload all materials through the normal API
4. wait for Worker parsing and indexing, then issue source-specific retrieval queries
5. draft, reject, redraft, approve, export, and retry through the durable run paths

Expected outcomes:

- all public documents are parsed and indexed
- retrieval returns a non-invalid locator for each expected public source
- the LangGraph and human-review workflow completes without a synthetic bypass
- evidence contains only IDs, counts, hashes, methods, and statuses

See [P0-D7 Public Procurement Rehearsal](public-procurement-rehearsal.md) for
the explicit legal and evaluation boundary.

## Scenario AC-08: Role-aware RFP and supplier-evidence rehearsal

Purpose:

- prove that buyer obligations and supplier supporting evidence remain separate
  control-plane facts rather than becoming one mixed LLM context bucket

Steps:

1. create an isolated project with a `buyer_rfp` bundle and a
   `supplier_evidence` bundle
2. parse and index both bundles through the ordinary Worker path
3. inspect the Requirement Ledger and confirm that only buyer source documents
   created requirement rows
4. draft a section that retrieves supplier evidence
5. link, verify, and approve a controlled factual claim through the public
   Requirement and Claim APIs
6. query readiness, then complete reject, redraft, approval, export, and retry

Expected outcomes:

- supplier wording never pollutes buyer requirements
- retrieved supplier material can become governed Evidence after review
- coverage and readiness change only after the explicit evidence and claim
  verification path
- the workflow and review lifecycle remains durable and retryable

See [P0-D8 Role-Aware Bid Rehearsal](role-aware-rehearsal.md).

## Release requirement

A release is not production-ready unless the scenarios relevant to its phase pass with current code and current docs.
