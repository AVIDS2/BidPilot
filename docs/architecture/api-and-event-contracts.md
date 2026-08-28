# API and Event Contracts

## Goal

Define stable contract rules for the API surface and internal async event shapes so implementation can move quickly without becoming inconsistent.

## API design conventions

### Resource style

- prefer durable business resources over generic action endpoints
- keep naming explicit and domain-oriented
- use plural nouns for collections and stable IDs for item routes

Examples:

- `/projects`
- `/projects/{project_id}/bundles`
- `/deliverables/{deliverable_id}/sections/{section_id}`
- `/execution-runs/{run_id}`

### Write behavior

- every write path returns durable identifiers
- long-running operations return an `execution_run_id`, `task_id`, or equivalent durable handle
- idempotent client retries should be supported where practical for create and trigger endpoints

### Response envelope

Use simple JSON responses unless a more specific contract is justified:

- resource payload for direct reads
- `data` plus stable metadata when pagination or expansion is involved
- explicit error shape for failures

### Error contract

All API errors should normalize to:

- `code`
- `message`
- `details`
- `request_id`

Preferred error code families:

- `validation_error`
- `not_found`
- `conflict`
- `forbidden`
- `unauthorized`
- `rate_limited`
- `upstream_failure`
- `internal_error`

## Async command and run contracts

### Long-running actions

The API should not pretend long-running work is synchronous.

Actions like parse, draft, rerun, validation, and export should:

1. create a durable run or task record
2. return that identifier immediately
3. update run state through the control plane

### Response-plan read model

The API exposes response-plan history as a project-scoped read model:

- `GET /response-plans?project_id=...` lists immutable plan revisions;
- `GET /response-plans/{response_plan_id}?project_id=...` returns sections,
  assigned requirement/owner snapshots, and the evidence/content-plan bindings
  used by each draft attempt.

Both endpoints require `project.read`. They are audit views only: clients do
not construct or mutate response-plan mappings directly.

### Run state shape

Each durable run should expose:

- `id`
- `project_id`
- `run_type`
- `status`
- `requested_by`
- `started_at`
- `finished_at`
- `input_summary`
- `output_summary`
- `provider_metadata`
- `error_summary`

### Run statuses

Use a stable status vocabulary:

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`
- `partial_success`

## Event contract conventions

### Event model

Events are append-only operational facts, not command messages.

Every event should contain:

- `event_id`
- `event_type`
- `occurred_at`
- `project_id`
- `actor`
- `subject`
- `payload`
- `schema_version`

### Naming style

Use past-tense domain events:

- `project.created`
- `bundle.registered`
- `document.parsed`
- `requirements.extracted`
- `section.drafted`
- `section.reviewed`
- `deliverable.exported`

### Subject shape

The event subject should identify what changed:

- `type`
- `id`
- optional `parent_type`
- optional `parent_id`

### Payload rules

- payloads may grow, but existing fields must not silently change meaning
- keep provider-specific raw payloads nested and clearly marked
- sensitive secrets never enter event payloads

## Contract versioning

- increment schema versions when a contract changes incompatibly
- additive fields are preferred over breaking renames
- shared contracts should live in `packages/contracts`
- API and worker code should import shared identifiers and enums where practical

## Assistant runtime event contract

Assistant and workflow execution traces use `RuntimeEventRecord` schema version
`1.2`. Every event is durable before it is rendered to SSE and includes a
run-local monotonic sequence plus optional parent-event lineage. Capability
events may include the provider-native `tool_call_id`; the browser uses it to
merge a live Pi tool start with its later durable result. Older events without
that field may use a scoped fallback only when there is one unambiguous open
tool in the same run.

The public assistant endpoint may still emit `assistant.*` events for
compatibility, but those events are projections of `run.*`, `capability.*`,
`approval.*`, `workflow.linked`, and `message.*` runtime facts. A terminal
assistant failure is projected as `assistant.session_error` plus a failed
`assistant.end`; a failure message is not rendered as a normal assistant answer.
If public text was already streamed, those partial deltas remain visible
separately from the terminal error.

See [assistant-harness-runtime.md](assistant-harness-runtime.md) for the
Harness lifecycle, idempotency, approval, and failure-handling rules.

## Documentation rule

Whenever a new top-level API domain or event family is introduced, update this document or create a focused follow-up contract doc nearby.
