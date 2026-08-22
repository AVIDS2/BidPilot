# Backend Application Architecture

> Runtime ownership note: the production conversational agent uses the Pi
> sidecar through `services/api/app/runtime`. The historical Python Harness
> and Operator graph remain replay-only compatibility code and are not an
> automatic fallback. See `services/api/app/runtime/README.md` for the import
> and migration boundary.

## Goal

Define the backend code structure and layering rules so the API and worker grow cleanly instead of turning into a service-shaped monolith.

## Runtime split

The backend consists of:

- `services/api`
- `services/worker`
- `services/pi-agent`
- shared contracts in `packages/contracts`

The split is by responsibility, not by framework preference:

| Unit | Owns | Must not own |
| --- | --- | --- |
| API control plane | Auth, domain commands/queries, capability registry, policy, approvals, idempotency, audit, `RuntimeRun`/`RuntimeEvent`, signed Pi bridge | Provider model loop, long-running parser/drafting work, browser state |
| Pi sidecar | Pi `AgentSession`, provider-native tool calls, streaming, retry/compaction, trusted extensions | Database/object-storage credentials, tenant authorization, direct business writes |
| Worker execution plane | Celery jobs, LangGraph ingestion/drafting/review/export graphs, durable continuation | HTTP route semantics, permission source of truth, direct browser interaction |
| Web client | REST/SSE projection, route state, feature UI and user actions | Business truth, agent intent routing, provider calls |

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
- `services/api/app/runtime`

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
- `runtime` (control-plane runtime services and the Pi bridge)

The runtime package is an API control-plane module, not the Pi model loop. New
Assistant requests enter `/assistant/stream`, are persisted by API services,
and are dispatched to `services/pi-agent` through the signed bridge contract.
The Pi sidecar never imports this Python package; it receives wire data only.

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
- `services/pi-agent` may depend on Pi packages and wire contracts, but never
  on SQLAlchemy, API routers, domain repositories, or tenant secrets
- frontend must not depend on backend internals outside documented contracts
- API routers must not import Worker LangGraph nodes; queue/service contracts
  are the boundary
- new code must not import the historical Python Harness/ReAct/operator loop

Historical Harness and operator modules remain only for replay compatibility.
They are not an Assistant implementation target and must not be used as a
fallback when the Pi sidecar is unavailable; failure is durable and explicit.

## Growth rule

When a module becomes too large, split within the application boundary before extracting a service.
