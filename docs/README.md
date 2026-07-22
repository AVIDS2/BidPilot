# DocPilot Documentation

This directory is the working source of truth for the `DocPilot` initiative.
It is organized to support three goals:

1. define the product clearly enough to stay stable while AI tooling changes
2. make architectural boundaries explicit so fast-moving AI components remain replaceable
3. give future implementers a staged path from empty repo to stable production system

## Documentation Map

### Core project docs

- `docs/superpowers/specs/2026-04-18-docpilot-design.md`
  - the formal design spec and project charter
- `docs/product/roadmap.md`
  - the staged delivery roadmap from phase 0 to phase 4
- `docs/product/mvp-scope.md`
  - the v1 boundary, success bar, and intentional exclusions
- `docs/product/non-functional-requirements.md`
  - production-grade quality, resilience, performance, and recovery expectations
- `docs/product/open-decisions-and-risks.md`
  - defaults, deferred decisions, and the conditions that justify revisiting them
- `docs/product/frontend-experience-principles.md`
  - the UX, layout, responsive, and interaction principles for the DocPilot workbench
- `docs/product/source-data-strategy.md`
  - supported source categories, document intake priorities, and data-quality rules
- `docs/product/domain-glossary.md`
  - durable domain terms and their intended meaning across product and implementation
- `docs/adr/0001-core-technology-stack.md`
  - the primary stack and architecture decision record
- `docs/adr/0002-workflow-and-execution-architecture.md`
  - the workflow engine decision, durable run model, and queue/orchestration split
- `docs/adr/0009-reviewed-memory-graph-projection.md`
  - the evidence, review, and evaluation gate required before graph proposals become persistent facts
- `docs/development/final-technology-baseline.md`
  - one-sheet implementation baseline summarizing the accepted stack and default choices

### Architecture docs

- `docs/architecture/overview.md`
  - system layers, request flows, and deployment evolution
- `docs/architecture/service-boundaries.md`
  - service boundaries and modular split rules
- `docs/architecture/data-model.md`
  - domain entities and storage rules
- `docs/architecture/integration-strategy.md`
  - how model providers, parsers, MCP servers, and tools plug into the system
- `docs/architecture/api-and-event-contracts.md`
  - REST, async run, and event contract conventions for stable implementation
- `docs/architecture/frontend-application-architecture.md`
  - route, state, UI layer, and component architecture for the frontend application
- `docs/architecture/document-ingestion-and-format-strategy.md`
  - supported file formats, ingestion pipeline, parser strategy, and export targets
- `docs/architecture/normalized-document-schema.md`
  - the canonical parsed document structure and chunk/evidence schema guidance
- `docs/architecture/execution-and-workflow-architecture.md`
  - execution lifecycle, task boundaries, state machine rules, and scheduler behavior
- `docs/architecture/backend-application-architecture.md`
  - backend module layout, layering rules, and service responsibilities
- `docs/architecture/repository-blueprint.md`
  - target repo structure and how code should be organized as implementation grows

### Operations docs

- `docs/ops/deployment-and-runbook.md`
  - environments, release flow, backup, migration, and incident handling
- `docs/ops/observability-and-sre.md`
  - telemetry, SLOs, alerts, tracing, and eval loops
- `docs/ops/release-checklist.md`
  - release gates for local, staging, and production promotion
- `docs/ops/environment-matrix.md`
  - differences, expectations, and controls across local, staging, and production

### Engineering docs

- `docs/development/engineering-standards.md`
  - repository structure, coding rules, and service ownership guidance
- `docs/development/local-development-workflow.md`
  - how to work locally from first clone to feature delivery
- `docs/development/local-environment-baseline.md`
  - the concrete local environment, ports, Docker services, conda env, and provider settings to use
- `docs/development/first-run-bootstrap-runbook.md`
  - first-day startup and environment verification before implementation begins
- `docs/development/development-preflight-checklist.md`
  - the checklist to pass before meaningful development or environment changes
- `docs/development/configuration-and-secrets.md`
  - environment variables, secret ownership, and config discipline
- `docs/development/agent-execution-manual.md`
  - how an implementation agent should choose work, sequence phases, and keep docs aligned
- `docs/development/current-execution-state.md`
  - the current active phase, current status, and where the next implementation session should start

### Quality and security docs

- `docs/quality/testing-strategy.md`
  - test pyramid, phase gates, fixtures, and evaluation responsibilities
- `docs/quality/acceptance-scenarios.md`
  - canonical end-to-end scenarios and release-grade acceptance flows
- `docs/quality/test-data-and-fixtures.md`
  - fixture packs, synthetic data rules, and repeatable validation datasets
- `docs/security/security-and-governance.md`
  - auth, RBAC, audit, secrets, and data handling rules

### Implementation plans

- `docs/superpowers/plans/2026-04-18-docpilot-phase-0-foundation.md`
  - repository bootstrap, environments, shared contracts, and local dev stack
- `docs/superpowers/plans/2026-04-18-docpilot-phase-1-bidpilot-core.md`
  - core BidPilot workflow: project workspace, ingestion, retrieval, evidence, drafting
- `docs/superpowers/plans/2026-04-18-docpilot-phase-2-governance-and-operations.md`
  - review flow, audit, observability, deployment, and operational hardening
- `docs/superpowers/plans/2026-04-18-docpilot-phase-3-production-hardening.md`
  - authentication, release automation, resilience, and operational maturity
- `docs/superpowers/plans/2026-04-18-docpilot-phase-4-scenario-expansion.md`
  - scenario package extraction and safe platform reuse beyond BidPilot

## Stable Core vs Replaceable Edge

The project is intentionally designed around a long-lived stable core and short-lived replaceable AI edge.

### Stable core

- product and business domain model
- project workspace and execution state machine
- PostgreSQL data model
- audit/event log
- evidence graph and review workflow
- frontend interaction model

### Replaceable edge

- model providers
- rerankers and embedding providers
- OCR and parsing engines
- agent runtime internals
- MCP client and server libraries
- prompt and eval strategies

## Current project identity

- Product name: `DocPilot`
- First scenario package: `BidPilot`
- Product category: `Enterprise AI Document Execution System`

## Primary architecture principles

- Business truth lives in `PostgreSQL`, not inside an agent framework.
- Agent orchestration is an execution detail, not the system source of truth.
- MCP is an integration boundary, not the internal platform bus.
- Every AI dependency must be wrapped behind an adapter interface.
- The system should begin as a well-structured modular application and only split into more services when load, ownership, or deployment pressure justifies it.
