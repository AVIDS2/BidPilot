# Backend Application Architecture

## Goal

Define the backend code structure and layering rules so the API and worker grow cleanly instead of turning into a service-shaped monolith.

## Runtime split

The backend consists of:

- `services/api`
- `services/worker`
- shared contracts in `packages/contracts`

## Backend principles

- API owns synchronous commands, queries, auth boundary, and durable run creation
- worker owns asynchronous execution, parser jobs, drafting jobs, validation jobs, and export jobs
- business truth stays in PostgreSQL
- adapters isolate external and AI-specific dependencies
- queue mechanics never replace durable run state

## API application structure

Preferred module layout:

- `services/api/app/main.py`
- `services/api/app/core`
- `services/api/app/db`
- `services/api/app/<domain-module>`

Each domain module should aim to contain:

- `router.py`
- `schemas.py`
- `service.py`
- `repository.py`
- `models.py` when scoped models are justified
- tests

## Suggested domain modules

- `projects`
- `bundles`
- `documents`
- `requirements`
- `retrieval`
- `execution`
- `deliverables`
- `review`
- `audit`
- `auth`
- `providers`

## Layer rules

### Router layer

Owns:

- HTTP request and response binding
- auth dependency entry
- schema validation at the request boundary

Does not own:

- business orchestration
- direct provider logic
- persistence-heavy workflows

### Service layer

Owns:

- business rules
- orchestration across repositories and adapters
- run creation logic
- transaction-aware command behavior

### Repository layer

Owns:

- persistence access
- query logic
- row-to-domain mapping support

Does not own:

- provider calls
- workflow decisions
- route semantics

### Adapter layer

Owns:

- provider integration
- parser integration
- retriever integration
- export rendering integration

Must return normalized contracts.

## Worker structure

Preferred module layout:

- `services/worker/app/celery_app.py`
- `services/worker/app/tasks`
- `services/worker/app/execution`
- `services/worker/app/adapters`

Task modules should stay thin:

- accept a durable identifier
- load required state
- invoke service or execution logic
- persist outcomes

## Transaction and state rules

- user-visible status changes should be written deliberately
- long-running operations should create a durable run before execution begins
- retries should not create silent duplicate business records
- immutable version records should be preferred over in-place overwrite for generated content

## Dependency rules

- API modules may depend on domain services, repositories, and contracts
- worker modules may depend on execution services, repositories, and adapters
- frontend must not depend on backend internals outside documented contracts

## Growth rule

When a module becomes too large, split within the application boundary before extracting a service.
