# Backend Contract Freeze For Frontend Rebuild

## Status

This is the backend boundary for the next frontend rebuild. Frontend work must
consume these public resources and runtime events; it must not query LangGraph
checkpoint tables, infer business state from model text, or duplicate policy
logic in the browser.

The contract is additive-first. New optional fields are allowed; a rename,
meaning change, or removal requires a new documented contract version and
backend regression coverage.

## Business resource APIs

| Domain | Primary read surface | Mutation / long-running surface | Frontend rule |
| --- | --- | --- | --- |
| Projects and bundles | `GET /projects`, `GET /bundles?project_id=...`, `GET /documents?bundle_id=...` | `POST /projects`, `POST /bundles`, `POST /documents/upload`, `POST /bundles/{id}/reingest` | Render durable project/document status only. |
| Requirement Ledger | `GET /requirements?project_id=...`, `GET /requirements/{id}` | Evidence, Claim, and Decision routes under `/requirements/{id}` | A requirement is a buyer obligation; never create a UI row from supplier material or model prose. |
| Evidence and retrieval | `GET /evidence?project_id=...`, `POST /retrieval/search` | none | Render source locator and safe excerpts, not raw chunk/model dumps. |
| Readiness | `GET /readiness/projects/{project_id}` | `POST /readiness/projects/{project_id}/packs` | Use `counts`, `scores`, and gap lists as the authoritative coverage display. |
| Drafting and review | `GET /execution/runs/{id}`, `GET /versions`, review reads | `POST /drafting/sections`, review decisions, retry/resume routes | Drafting is asynchronous; wait on durable run state/events. |
| Export | export record reads | `/export/...` and readiness-pack download routes | Download via authenticated Blob request only. Do not expose object keys. |

## Runtime and SSE contract

The unified runtime is the only product progress source:

- `GET /runtime/runs?conversation_id=...` lists visible work.
- `GET /runtime/runs/{run_id}` returns the durable run and linked workflow
  runs.
- `GET /runtime/runs/{run_id}/events?after_sequence=N` replays ordered,
  persisted events.
- `POST /runtime/runs/{run_id}/cancel` records cancellation intent.
- `POST /runtime/approvals/{approval_id}/resolve` resolves non-operator
  approval records; interactive operator approvals resume through the
  Assistant endpoint.
- `POST /assistant/stream` remains the compatibility streaming entry point;
  it projects the same runtime facts to `assistant.*` SSE events.
- `GET /drafting/runs/{run_id}/stream` is workflow-node detail only. It may
  enrich a run view but cannot replace runtime lifecycle state.

Stable event types are declared in `packages/contracts/runtime.py`:

```text
run.started
plan.proposed / plan.updated
capability.started / capability.progressed / capability.succeeded / capability.failed
approval.requested / approval.resolved
workflow.linked
message.delta / message.completed
run.completed / run.failed / run.cancelled
```

Event ordering is `sequence` scoped to `run_id`. Store the highest rendered
sequence client-side and reconnect with `after_sequence`; never deduplicate by
message text or timestamps.

## Non-negotiable renderer rules

1. Render user-facing capability labels and safe public summaries, never raw
   tool name, JSON arguments, ORM fields, provider payload, prompt, stack
   trace, storage key, or database ID.
2. Show a capability state before final response prose when events arrive in
   that order. Completed adjacent operations may be grouped, but failure and
   approval boundaries must stay visible.
3. A browser-provided approval mode, project id, or model choice is a request,
   not a permission grant. The server policy and organization/project access
   check are authoritative.
4. The UI must express missing evidence honestly. It must not turn an absent
   Evidence row into a positive coverage claim.
5. Domain state lives in PostgreSQL. LangGraph checkpoints are recovery
   internals and are not a frontend API.

## Backend release gate before frontend integration

The frontend can use this contract after all are green:

- migration health on a dedicated `_test` database;
- API and Worker regression suites for requirement/evidence/readiness/runtime;
- P0-D7 public historical procurement rehearsal;
- P0-D8 role-aware buyer-RFP-to-supplier-evidence rehearsal;
- no raw runtime/tool output in API or SSE contract tests.

Implementation anchors: `services/api/app/runtime/`,
`services/api/app/requirements/`, `services/api/app/readiness/`,
`services/api/app/evidence/`, `services/api/app/drafting/`, and
`packages/contracts/runtime.py`.
