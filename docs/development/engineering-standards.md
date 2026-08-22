# Engineering Standards

## Objective

Keep implementation quality high while allowing fast iteration across AI-heavy components.

## Repository layout target

- `apps/web`
- `services/api`
- `services/worker`
- `packages/contracts`
- `docs`
- `scripts`

## Ownership model

### `apps/web`

Owns:

- user-facing workbench
- review surfaces
- drafting UX
- audit visibility

### `services/api`

Owns:

- domain commands and queries
- data persistence
- auth and RBAC
- audit write path

### `services/worker`

Owns:

- parsing
- indexing
- drafting execution
- export jobs

### `services/pi-agent`

Owns:

- Pi `AgentSession` and provider-native model/tool streaming
- compiled, allowlisted Pi extensions

Does not own:

- database, object-storage, tenant-key, or browser access
- authorization, approvals, audit, or business writes

### `packages/contracts`

Owns:

- shared schemas
- identifiers
- event contracts

### Runtime rule

The only new interactive Assistant implementation is the Pi sidecar reached
through the API control plane. The API owns auth, capability governance,
approval, audit, idempotency, and durable runtime events. The Worker owns
long-running LangGraph workflows. The Web client renders the public REST/SSE
projection. These boundaries are enforced in code review and must not be
recreated as a second loop in a feature module.

## Coding rules

- business rules live in domain services, not route handlers
- provider-specific logic stays behind adapters
- worker jobs write meaningful outcomes back into relational state
- all generated outputs must be versioned, not overwritten in place
- audit events are append-only

## API design rules

- prefer explicit nouns and verbs over vague generic endpoints
- use stable IDs in all write paths
- every async operation returns a durable run or task identifier
- do not expose provider-specific payloads as the primary API response shape

## Frontend rules

- feature folders mirror durable product concepts
- shared UI primitives remain separate from feature logic
- review state and execution state should be read from API models, not reconstructed ad hoc
- keep optimistic updates limited to low-risk interactions

## Backend rules

- SQLAlchemy models mirror stable domain objects
- Pydantic schemas define external API contracts
- service layer owns orchestration between repositories and adapters
- repository layer owns persistence only
- Pi sidecar code must not import API ORM/domain modules; use the signed bridge
- API routers must not import Worker graph nodes; use durable command/task IDs
- historical `harness_*` and `operator_*` modules are replay-only and receive
  no new features

## Job execution rules

- jobs must be idempotent where feasible
- retries must preserve traceability
- long-running tasks must update durable run state
- raw provider failures must be normalized before they reach domain services

## Documentation rules

- each new subsystem needs a short ADR or an update to an existing ADR when it changes a foundational choice
- user-facing workflows should update product or roadmap docs when scope changes
- operational behavior changes must update the runbook

## Change control

- do not add a new infrastructure dependency without a clear owner and local development story
- do not split a module into a service before the extraction rules in `docs/architecture/service-boundaries.md` are met
- do not widen product scope beyond BidPilot until Phase 2 is complete
