# Service Boundaries

## Boundary philosophy

DocPilot should not start as a microservice maze. It should start as a disciplined modular system with clean extraction points.

## Initial runtime units

### `apps/web`

Responsibilities:

- authenticated workbench UI
- project navigation
- drafting and review interface
- execution and audit visibility

Does not own:

- business truth
- execution orchestration
- parsing or provider logic

### `services/api`

Responsibilities:

- REST API
- auth boundary
- domain commands and queries
- validation and persistence
- scheduling of async work

Does not own:

- heavy parsing
- long-running drafting
- provider-specific business logic

### `services/worker`

Responsibilities:

- async job consumption
- parser and indexing work
- execution graph runs
- export rendering

Does not own:

- direct user interaction
- permission policy source of truth

### `packages/contracts`

Responsibilities:

- API request and response contracts
- event schemas
- shared enums and identifiers

## Internal module split inside `services/api`

- `projects`
- `bundles`
- `documents`
- `retrieval`
- `execution`
- `review`
- `deliverables`
- `audit`
- `auth`
- `providers`

Each module should expose:

- API schemas
- domain service
- repository layer
- tests

## Extractable future services

These may become standalone later, but should begin as modules:

- execution gateway
- connector gateway
- export renderer
- evaluation service

## Extraction rules

Extract a module into a service only if at least one of these is true:

- independent scaling is required
- deployment cadence differs materially
- ownership must be split across teams
- runtime characteristics differ enough to justify isolation

## Explicit anti-patterns

- letting LangGraph own domain state
- storing critical workflow status only in Redis
- embedding provider-specific formats in domain tables
- coupling frontend routes to worker internals
