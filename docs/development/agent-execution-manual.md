# Agent Execution Manual

## Goal

Provide one operational manual for a long-running implementation agent working in `DocPilot`.

This is the document that turns the rest of the documentation set into a practical execution system.

## Core rule

Build in phase order. Do not treat the roadmap as a bag of optional ideas.

## Source of truth order

When documents differ, use this priority:

1. `docs/superpowers/specs/2026-04-18-docpilot-design.md`
2. `docs/product/mvp-scope.md`
3. `docs/product/roadmap.md`
4. current phase plan in `docs/superpowers/plans/`
5. ADRs and architecture docs
6. engineering, quality, security, and ops docs

If two documents conflict materially, pause and update the docs before continuing implementation.

## Execution loop for each session

1. identify the active phase
2. read the current phase plan and relevant supporting docs
3. choose the next unchecked or unimplemented slice that unblocks future work
4. verify uncertain APIs, schema details, or tool usage before coding
5. implement the smallest coherent slice
6. run the best available verification
7. update docs if architecture, operations, scope, or contracts changed
8. leave the repository in a state the next session can continue from

For meaningful frontend work, also read:

- `docs/product/frontend-experience-principles.md`
- `docs/architecture/frontend-application-architecture.md`

For meaningful ingestion, parser, retrieval, or evidence work, also read:

- `docs/product/source-data-strategy.md`
- `docs/architecture/document-ingestion-and-format-strategy.md`
- `docs/architecture/normalized-document-schema.md`

For meaningful workflow, queue, execution-run, or export-pipeline work, also read:

- `docs/adr/0002-workflow-and-execution-architecture.md`
- `docs/architecture/execution-and-workflow-architecture.md`

For repository structure, backend layering, or environment-shape work, also read:

- `docs/development/final-technology-baseline.md`
- `docs/architecture/backend-application-architecture.md`
- `docs/architecture/repository-blueprint.md`
- `docs/ops/environment-matrix.md`

## Phase discipline

### Phase 0

Allowed focus:

- repository skeleton
- local stack
- migrations
- contracts
- health checks
- CI skeleton

Avoid:

- scenario-specific gold plating
- provider-specific complexity that is not yet needed

### Phase 1

Allowed focus:

- BidPilot core workflow
- ingestion, parsing, retrieval, evidence, drafting

Avoid:

- advanced scenario expansion
- production auth and multi-tenant design beyond placeholders

### Phase 2

Allowed focus:

- review workflow
- audit visibility
- export pipeline
- governance surfaces

### Phase 3

Allowed focus:

- auth and RBAC
- deployment automation
- backup and restore
- hardening and resilience

### Phase 4

Allowed focus:

- controlled reuse of the platform core for new scenario packages

## Task selection rule

Prefer tasks that:

- unlock the next phase dependency
- make acceptance scenarios pass
- reduce long-term architecture drift
- improve production credibility

Defer tasks that are:

- cosmetic but not blocking
- speculative abstraction
- second-scenario work before BidPilot is complete

## Documentation update rule

Update docs in the same change when:

- a foundational technology choice changes
- a new API or event family is introduced
- a runbook or operational behavior changes
- a non-functional target changes
- a deferred decision becomes active

## Completion rule

Do not mark a task effectively done unless:

- code is implemented
- relevant tests or smoke checks ran
- docs are still aligned
- the next implementer can tell what changed and what remains

## If blocked

When blocked by an unresolved decision:

1. check `docs/product/open-decisions-and-risks.md`
2. use the current default if the trigger has not been met
3. if the trigger has been met, update docs first or leave a precise blocker note

## Final principle

Optimize for continuous, reviewable progress toward a production system, not bursts of impressive but disconnected implementation.
