# DocPilot Roadmap

## Planning horizon

This roadmap covers the expected path from empty repository to stable production deployment. It is designed for iterative implementation across multiple sessions while keeping the architecture stable for at least two years.

## Phase 0: Foundation

### Objective

Create a durable engineering base for all future work.

### Deliverables

- mono-repo layout with frontend, API, worker, and shared contracts
- local Docker-based development stack
- PostgreSQL schema baseline
- Redis and object storage integration
- telemetry baseline
- CI skeleton

### Exit criteria

- all services boot locally through one command
- migrations run cleanly
- one health check spans web, API, worker, database, and storage

## Phase 1: BidPilot Core

### Objective

Ship the first complete scenario workflow from project creation to evidence-backed drafting.

### Deliverables

- project workspace
- bundle upload and source document registry
- parse and indexing pipeline
- requirement matrix extraction
- evidence graph
- section drafting UI and API

### Exit criteria

- one realistic bundle can be ingested end-to-end
- at least one output section is generated with evidence references
- rerunning a section preserves trace and version history

## Phase 2: Review, Governance, and Export

### Objective

Make the product operationally credible, not just technically impressive.

### Deliverables

- review threads
- approval and rejection workflow
- version diff and change reasoning
- audit event stream
- cost and trace view
- export pipeline for final artifacts

### Exit criteria

- a reviewer can approve or reject section output in-system
- the system can show who changed what, when, and why
- a final deliverable can be exported from approved content

## Phase 3: Production Hardening

### Objective

Make the system safe to run continuously in a real environment.

### Deliverables

- authentication and RBAC
- deployment automation
- backup and restore
- environment promotion strategy
- observability dashboards and alerting
- incident and rollback procedures

### Exit criteria

- a staging deployment can be recreated from documented steps
- backups and restore are tested
- error budgets and SLOs are defined

## Phase 4: Scenario Expansion

### Objective

Reuse the platform core without corrupting the original domain model.

### Candidate expansions

- contract review package
- delivery acceptance package
- regulated document response package

### Exit criteria

- one additional scenario package can be implemented without redesigning the control plane

## Strategic rules

- No new scenario package before BidPilot is complete through review and export.
- No new infrastructure service unless load, ownership, or deployment constraints justify it.
- All AI dependencies remain adapter-based and replaceable.
- Control plane and audit model are never skipped for speed.
