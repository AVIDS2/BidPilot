# Testing Strategy

## Objective

Ensure DocPilot remains stable as AI dependencies and workflow complexity grow.

## Testing philosophy

Tests should protect:

- domain correctness
- workflow durability
- evidence traceability
- review and approval logic
- deployment confidence

## Test layers

### Unit tests

Focus:

- domain services
- adapters with fakes
- validation logic
- frontend pure components

### Integration tests

Focus:

- API with database
- worker with queue and storage stubs
- parser and drafting pipeline boundaries
- export flow

### Contract tests

Focus:

- API request and response schemas
- event payloads
- adapter normalization contracts

### End-to-end tests

Focus:

- create project
- upload bundle
- extract requirements
- draft section
- review section
- export deliverable

### Evaluation tests

Focus:

- evidence presence
- response quality rubrics
- parser regression
- provider comparison

### Load smoke tests

Focus:

- API availability under short local concurrency bursts
- P95 latency checks for liveness and schema endpoints
- fast failure on non-2xx responses before release candidates

## Current Commands

- Web unit and component tests: `pnpm --dir apps/web test` (Vitest + jsdom)
- Web typecheck/build: `pnpm --dir apps/web typecheck` and
  `pnpm --dir apps/web build`
- Pi sidecar contract tests: `pnpm --dir services/pi-agent test`
- API and Worker tests require an isolated database whose name ends in
  `_test`. The local direct-process profile does not start Docker, MinIO or a
  broker; storage/queue integration belongs to the VPS or an approved
  PostgreSQL/Redis/MinIO acceptance environment.

## Phase gate expectations

### Phase 0

- health checks
- schema and migration tests
- local stack smoke test

### Phase 1

- project CRUD tests
- bundle registration tests
- drafting entrypoint tests
- one end-to-end local scenario

### Phase 2

- review decision tests
- audit event tests
- export smoke tests

### Phase 3

- auth and RBAC tests
- backup and restore drill validation
- deployment smoke checks

### Phase 4

- scenario package compatibility tests
- regression tests to prove BidPilot behavior remains intact

## AI-specific test rules

- do not assert fragile provider wording unless the response is fully mocked
- assert evidence linkage, schema shape, and workflow state before stylistic phrasing
- store prompt and adapter version metadata for reproducible evals

## Minimum CI bar

- unit and integration tests for touched modules
- lint or type-check for changed services
- one API smoke test
- one worker smoke test when async flow changed

## Release bar

Before a release candidate:

- run the full end-to-end scenario
- run the local load smoke script
- verify export path
- verify audit and trace visibility
- review error budget and open regressions
- verify the relevant scenarios in `docs/quality/acceptance-scenarios.md`
