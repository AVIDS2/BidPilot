# Assistant Harness Runtime Boundary

> Status: P0 baseline, 2026-07-26

## Purpose

BidPilot has two different AI execution modes. They solve different problems
and must not silently replace each other:

| Mode | Owner | Use it for |
| --- | --- | --- |
| Assistant Harness | `StreamingHarness` | A user conversation that selects one product capability at a time, reads results, asks for missing input, and obtains approval for governed actions. |
| LangGraph workflow | API + worker + `ExecutionRun` | Long-running bid pipelines such as document ingestion, drafting, validation, review, and export. |

The public `/assistant/stream` endpoint always resolves to the governed
Harness. Historical `operator` and `streaming_harness` environment values are
compatibility aliases, not alternate public runtimes.

## Runtime inventory and migration boundary

| Entry | Production status | Boundary / removal plan |
| --- | --- | --- |
| `/assistant/stream` -> `StreamingHarness` | Supported public Assistant path | The only endpoint allowed to create a new `assistant_turn`. |
| `/assistant/attachments` | Supported companion API | Stages private attachment metadata; it cannot execute tools or start an agent loop. |
| `runtime/operator_adapter.py` | Internal compatibility facade | It renders the durable SSE projection and dispatches new turns to `StreamingHarness`; it is not a second HTTP entry point. |
| `runtime/operator_graph.py` | Historical-run compatibility only | New public turns never create `langgraph_operator` runs. Retain only to finish/resume historical durable runs, then remove after **2026-09-30**. |
| `agent/graph.py` | Legacy ReAct compatibility only | No production route imports it. Retain only for temporary checkpoint-policy coverage; remove after **2026-09-30** unless a migration dependency is recorded. |
| Worker LangGraph graphs | Supported workflow engine | These are not Assistant routes. They execute durable `ExecutionRun` workflows for ingestion, drafting, validation and review resume. |

Production configuration must set `DOCPILOT_ASSISTANT_ENGINE=harness`.
`operator` and `streaming_harness` are configuration-parser aliases only and
must not be used in new deployment files. Historical development notes may
refer to the older operator path; this inventory is the current authority.

## Harness turn lifecycle

1. The browser sends a new `client_request_id` for each submit.
2. The API resolves the project boundary, staged attachments, and a complete
   server-side or encrypted BYOK model configuration.
3. A `RuntimeRun(kind=assistant_turn)` is created before any capability runs.
4. The Harness streams native model tool calls. One capability is executed per
   model turn; campaign work uses the dedicated `run_section_campaign` tool
   rather than a burst of independent writes.
5. Every capability goes through authorization, policy, audit, and durable
   runtime events. The model never bypasses a product service.
6. The assistant response, terminal state, and public event summaries are
   persisted in PostgreSQL. SSE is a live projection of that durable trace.

## Pauses and approval

- Missing required input persists `ChatTaskState(status=needs_input)` and
  stops the current turn. It does not create a fake tool failure or execute a
  partially populated action.
- Costing, write, and destructive capabilities go through runtime policy.
  `RuntimeApproval` is the durable approval record; text confirmation is only
  a UI/input method, never the authority itself.
- Destructive actions can require typed confirmation even in `full_access`.
- A workflow started by a capability creates a `RuntimeRun(kind=workflow_bridge)`
  linked to its parent assistant turn and to the worker `ExecutionRun`.

## Idempotency and retry

`client_request_id` is scoped and hashed with the initiating user. A normal
transport retry checks for the existing runtime run before attachment
hydration, provider resolution, usage accounting, or conversation allocation,
then replays its durable events. `create_or_get_runtime_run` also has a unique
database-backed race fallback, so a duplicate request cannot execute a second
capability run.

Approval resolution is a separate operation keyed by `approval_id`; it must
not reuse the original submit ID as a new assistant turn.

## Model boundary and failure handling

- Platform keys remain server-side. BYOK keys are decrypted only for the
  provider call and are never sent to the browser, events, or logs.
- A model configuration must have an explicit provider protocol, endpoint,
  key, and model. No placeholder key or guessed fallback model is allowed.
- If a provider error occurs after SSE has begun, the API records a durable
  `run.failed` with a redacted, user-facing message and emits the normal
  `assistant.message` plus `assistant.end` sequence. Raw gateway errors and
  provider details are not exposed to the client.
- Supported reasoning levels are exactly `low`, `medium`, `high`, `extra`,
  and `max`. Adapter mappings may reduce unsupported provider levels, but the
  public vocabulary does not change per provider.

## Event contract

`RuntimeEventRecord` schema version `1.1` is the source for assistant and
workflow execution traces. Each event has:

- `event_id`, `run_id`, optional `parent_event_id`
- monotonic `sequence` within one run
- `created_at`, `type`, `public_summary`, and redacted `payload`

Core events are `run.started`, `plan.updated`, `capability.*`,
`approval.*`, `workflow.linked`, `message.*`, and terminal `run.*` events.
The legacy `assistant.*` SSE names are a compatibility projection only; new
backend work should produce durable runtime events first.

## Non-goals of this baseline

- The Harness is not an unconstrained coding agent and cannot execute shell,
  server, or arbitrary network commands.
- LangGraph checkpoint state is not business truth. Product state, approvals,
  messages, audits, and run history live in PostgreSQL.
- This does not yet replace the knowledge plane. Retrieval and memory adapters
  remain separate from the Harness boundary and can later be integrated with a
  production knowledge system without changing the run contract.

## Required regression coverage

Before changing this runtime, preserve tests for:

- missing-field pause and later resume
- approval, typed destructive confirmation, and cancellation
- durable event ordering and replay
- client retry without duplicate model execution, transcript messages, or
  usage event in the ordinary retry path
- attachment hydration from server-owned staged metadata
- redacted provider/model failures after the SSE stream starts
- workflow bridge linkage between assistant run and worker execution

## External MCP tools (sensing extensions)

The Harness can load read-style tools from allowlisted external MCP servers.
This follows the trust boundary in AI-Agents-in-Depth 4.3:

- **Allowlist only** — servers must be listed in `DOCPILOT_MCP_SERVERS`.
- **Namespace prefix** — every tool is exposed as `mcp_<server>_<tool>` so a
  remote server cannot shadow a product capability.
- **Sensing-only by default** — MCP tools are read boundaries. Mutations still
  go through `execute_capability` (approval / quota / tenant / audit). Mark a
  server `"trusted_mutations": true` only when you explicitly trust it.
- **Degradation** — an unreachable server is skipped and never blocks a turn.

### Configuration

`DOCPILOT_MCP_SERVERS` is a JSON array. API keys are passed per server via the
`env` map and must be referenced from deployment secrets, never committed:

```json
[
  {
    "name": "tavily",
    "command": "npx",
    "args": ["-y", "tavily-mcp"],
    "env": { "TAVILY_API_KEY": "${TAVILY_API_KEY}" }
  }
]
```

`DOCPILOT_MCP_TRUSTED_MUTATIONS` is a comma-separated list of server names that
may expose mutation tools.

### Skills (progressive disclosure)

Skills live under `docs/agent-skills/<name>/SKILL.md` with standard YAML
frontmatter (`name`, `description`). The Harness loads Level-1 metadata
(name + description) into `AVAILABLE_SKILLS` every turn and reads the selected
skill body (Level 2) only when routed. Routing runs against the description
(English + Chinese fragments) plus a legacy trigger table, ranked by
specificity.

Current skills:

- `bid-outline-first` — resolve outline `section_key` before drafting
- `bid-research` — external research, fetch pages into project, cite
- `bid-tender-writer` — five-stage tender technical response workflow
