# Assistant Harness Runtime Boundary

> Status: Pi runtime implemented; real-model and production acceptance pending, 2026-08-18

## Purpose

BidPilot has two different AI execution modes. They solve different problems
and must not silently replace each other:

| Mode | Owner | Use it for |
| --- | --- | --- |
| Assistant Harness | Pi `Agent` (`services/pi-agent`) | A user conversation that decides with provider-native tool calls, reads structured observations, asks for missing input, and obtains approval for governed actions. |
| LangGraph workflow | API + worker + `ExecutionRun` | Long-running bid pipelines such as document ingestion, drafting, validation, review, and export. |

The public `/assistant/stream` endpoint resolves to the Pi runtime. Historical
`operator`, `harness`, and `streaming_harness` values are parser aliases to Pi,
not alternate public runtimes. There is no automatic fallback to the retired
Python loop: an unavailable Pi sidecar produces a durable, diagnosable failure.

## Runtime inventory and migration boundary

| Entry | Production status | Boundary / removal plan |
| --- | --- | --- |
| `/assistant/stream` -> Pi sidecar | Supported public Assistant path | The only endpoint allowed to create a new `assistant_turn`; it projects Pi events onto the durable runtime trace. |
| `/assistant/attachments` | Supported companion API | Stages private attachment metadata; it cannot execute tools or start an agent loop. |
| `runtime/operator_adapter.py` | Internal compatibility facade | It owns preflight/idempotency and dispatches new turns to Pi; it is not a second HTTP entry point. |
| `services/pi-agent` | Supported model loop | Pi owns model turns, native streaming, parallel independent read tools, tool lifecycle, and bounded continuation. It has no database credentials. |
| `/internal/pi/tools/execute` | Internal bridge | Run-scoped token only. The existing BidPilot adapter remains authoritative for permissions, approvals, idempotency, audit and business writes. |
| `runtime/operator_graph.py` | Historical-run compatibility only | New public turns never create `langgraph_operator` runs. Retain only to finish/resume historical durable runs, then remove after **2026-09-30**. |
| `agent/graph.py` | Legacy ReAct compatibility only | No production route imports it. Retain only for temporary checkpoint-policy coverage; remove after **2026-09-30** unless a migration dependency is recorded. |
| Worker LangGraph graphs | Supported workflow engine | These are not Assistant routes. They execute durable `ExecutionRun` workflows for ingestion, drafting, validation and review resume. |

Production configuration must set `DOCPILOT_ASSISTANT_ENGINE=pi` and provide
`DOCPILOT_PI_AGENT_URL`, `DOCPILOT_PI_TOOL_BRIDGE_URL`, and a dedicated
`DOCPILOT_PI_INTERNAL_SECRET` (the JWT secret is a local-development fallback
only). Historical development notes may refer to the older Python loop; this
inventory is the current authority.

## Harness turn lifecycle

1. The browser sends a new `client_request_id` for each submit.
2. The API resolves the project boundary, staged attachments, and a complete
   server-side or encrypted BYOK model configuration.
3. A `RuntimeRun(kind=assistant_turn)` is created before any capability runs.
4. Pi streams native model text/tool events. Independent read-only calls may
   execute in parallel; mutating calls are sequential and each goes through the
   internal bridge. Campaign work uses the dedicated `run_section_campaign`
   tool rather than a burst of independent writes.
5. Every capability goes through authorization, policy, audit, and durable
   runtime events. The model never bypasses a product service.
6. The assistant response, terminal state, and public event summaries are
   persisted in PostgreSQL. SSE is a live projection of that durable trace.

## Pi prompt and resource assembly

The Pi sidecar receives a small, composable system prompt rather than a
natural-language keyword router. The implementation reference is the
MIT-licensed
`badlogic/pi-mono` `packages/coding-agent/src/core/system-prompt.ts` (reviewed
at commit `936aff0`). BidPilot adapts the identity and product boundary but
keeps the same architecture:

1. a stable assistant identity and a short set of general execution rules;
2. provider-native tool schemas supplied separately from the prose prompt;
3. trusted runtime/project context assembled near the current turn;
4. a small `AVAILABLE_SKILLS` index, with full instructions loaded on demand
   through the real `read_skill` tool.

The server must not infer a capability, force a required tool call, or select
a Skill by matching words in the user message. The model chooses tools from
their schemas. Runtime code remains responsible for validation, authorization,
approval, quotas, idempotency, loop bounds, and truthful failure handling.
When a requested action has enough input, the model invokes the action tool;
it does not imitate an approval request in assistant prose. Policy may then
create a durable `RuntimeApproval` and pause the run.

A previous non-retryable action outcome is appended as a trusted,
argument-free `PREVIOUS_TERMINAL_ACTION` block on the next turn. This gives the
model the failure fact needed to answer a follow-up without replaying the old
action or exposing its stored parameters.

## Pauses and approval

- Missing required input persists `ChatTaskState(status=needs_input)` and
  stops the current turn. It does not create a fake tool failure or execute a
  partially populated action.
- Costing, write, and destructive capabilities go through runtime policy.
  `RuntimeApproval` is the durable approval record; text confirmation is only
  a UI/input method, never the authority itself.
- Destructive actions can require typed confirmation even in `full_access`.
- `approval_mode=full_access` means that optional confirmation prompts may be
  skipped. It never bypasses account authorization, tenant boundaries, plan
  quotas, required inputs, idempotency, or destructive-action safeguards. The
  product label is `Auto-run` / `自动执行` so this boundary is explicit.
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
- Capability failures are classified into stable public error codes before
  they are returned to the model or user. Non-recoverable business outcomes
  such as `project_limit_exceeded`, invalid input, forbidden access, missing
  resources, and state conflicts terminate the run after the first attempt.
  They must not enter the generic consecutive-failure retry loop.

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

The browser restores transcript messages and all recent run-event streams in
parallel, merges them by durable time/sequence, and commits one conversation
snapshot. This prevents a transcript from rendering first and execution
history jumping in later. Timeline groups are collapsed by default at every
level and are never opened or closed by incoming events; only the user changes
disclosure state. Running/thinking aggregate labels may use a restrained
motion treatment, while completed or failed labels remain static.

## Non-goals of this baseline

- The cloud sidecar is not given a tenant's raw server shell. A future local or
  private-deployment companion may expose a workspace-scoped Bash tool with
  explicit approval, timeout, audit and output limits; cloud business tools do
  not imply arbitrary host access.
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
- one-attempt termination for non-recoverable capability failures, including
  project plan limits even when approval mode is `full_access`
- dynamic Skill loading without keyword routing, duplicate-search suppression,
  research convergence, and one nested public task timeline

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
(name + description) into `AVAILABLE_SKILLS` every turn. The model selects a
skill by meaning and calls the server-owned `read_skill(name)` tool to load its
Level-2 body. The server accepts only an exact allowlisted skill name. Product
code must not route skills by matching user-message keywords.

Current skills:

- `bid-outline-first` — resolve outline `section_key` before drafting
- `bid-research` — external research, fetch pages into project, cite
- `bid-tender-writer` — five-stage tender technical response workflow
- `opportunity-deep-research` — read-only opportunity research with official
  source verification, explicit search budgets, deduplication, and convergence

### Research convergence

Read-only opportunity research is one public parent task, not a flat list of
search turns. The Harness deduplicates normalized queries, permits at most six
search calls, and closes research after two rounds without a new source. The
model then receives a trusted instruction to synthesize the answer and mark
unknown facts as pending verification. If it still requests searches three
times after the boundary, the Harness terminates the loop with a concise public
message. Search counts and raw queries remain model/system observations; the
user timeline shows sources, verification progress, and the final evidence-
backed answer.
