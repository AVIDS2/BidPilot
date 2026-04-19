# Open Decisions and Risks

## Goal

Record the important decisions that are intentionally deferred, along with the current default and the trigger for revisiting them.

This keeps future implementers from inventing permanent answers too early.

## Working rule

If a topic is listed here, use the documented default until the revisit trigger is met.

## Decision register

### Authentication provider

- current default: simplified development auth in local and early staging work
- revisit trigger: before Phase 3 staging hardening or before any external user access
- decision scope: hosted auth provider vs self-managed identity stack

### Tenant model

- current default: single-tenant operational model with project-level isolation
- revisit trigger: first requirement for multiple customer organizations in one deployment
- decision scope: tenant isolation boundaries, tenant IDs, tenant-aware RBAC, storage partitioning

### Retrieval backend

- current default: `PostgreSQL + pgvector` with room for lexical or hybrid retrieval
- revisit trigger: corpus size, latency, or relevance quality exceeds acceptable thresholds
- decision scope: keep pgvector only vs add dedicated search infrastructure

### Deployment substrate

- current default: local `Docker Compose`, production path documented as hardened container deployment
- revisit trigger: environment count, team count, or operational complexity makes current deployment unsafe or too manual
- decision scope: Compose-based ops vs Kubernetes or managed platform

### Provider portfolio

- current default: one OpenAI-compatible provider and one domestic provider through a shared adapter contract
- revisit trigger: compliance, cost, latency, or quality requirements justify additional providers
- decision scope: supported provider matrix and failover behavior

### Export formats

- current default: approved deliverable export pipeline exists before format expansion
- revisit trigger: first real delivery requirement for strict format fidelity
- decision scope: markdown/html only vs docx/pdf/native office generation

### Parser stack

- current default: one parser pipeline behind the parser adapter with stable normalized output
- revisit trigger: layout quality, OCR accuracy, or table extraction quality is not adequate for acceptance scenarios
- decision scope: parser replacement vs multi-parser routing

## Risk register

### Risk: AI adapter churn leaks into business logic

- mitigation: adapter contracts stay explicit; provider payloads are normalized before domain services

### Risk: continuous development drifts away from product scope

- mitigation: roadmap, MVP scope, and this register define the current boundary; no new scenario before BidPilot is complete through export

### Risk: local-only success hides production gaps

- mitigation: acceptance scenarios, NFR targets, release checklist, and runbook must all pass before a production claim

### Risk: schema evolves without migration discipline

- mitigation: all schema changes flow through Alembic; migrations and model updates are reviewed together

### Risk: doc drift makes agentic development unreliable

- mitigation: every foundational change updates the relevant doc before or with the implementation
