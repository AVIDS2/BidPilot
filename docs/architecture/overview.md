# Architecture Overview

## System intent

DocPilot is a project-centric execution system for complex document workflows. The architecture is designed so that business state stays stable while parsers, models, and AI runtimes evolve.

## High-level layers

### Web application

Owns:

- project workbench
- bundle and document views
- requirement matrix view
- section drafting and review
- audit and observability surfaces

### API application

Owns:

- authentication boundary
- project and document CRUD
- execution scheduling endpoints
- review and approval APIs
- export orchestration requests

### Worker application

Owns:

- parsing jobs
- indexing jobs
- evidence generation jobs
- drafting jobs
- validation and export jobs

### Data services

- PostgreSQL for durable business and audit state
- Redis for queueing, ephemeral state, and caching
- MinIO/S3 for raw and rendered artifacts

## Plane model

### Control plane

The control plane stores durable state and commands. It is the product core.

### Execution plane

The execution plane runs long-lived or asynchronous operations and reports results back to the control plane.

### Integration plane

The integration plane exposes stable interfaces to model providers, parsers, vector retrieval, and external tools.

### Operations plane

The operations plane handles deployment, tracing, alerts, and runbooks.

## Request flow

1. user creates a project
2. user uploads a bundle
3. API stores document metadata and objects
4. API emits ingest jobs
5. worker parses and indexes documents
6. execution service creates requirement and evidence artifacts
7. user launches section drafting
8. worker runs drafting graph and writes outputs and evidence links
9. reviewer comments, rejects, or approves
10. approved content is exported into a deliverable package

## Deployment evolution

### Initial mode

A modular single deployment with:

- `web`
- `api`
- `worker`
- `postgres`
- `redis`
- `minio`

### Later mode

Split only where justified:

- separate execution service
- connector service
- scheduler service
- dedicated observability stack

## Stability strategy

The architecture is considered stable if the following survive framework churn:

- project, task, deliverable, evidence, and review data model
- adapter interfaces
- queue and job contracts
- audit event format
- frontend interaction model
