# Assistant Harness Runtime Boundary

> Status: Pi `AgentSession`, trusted dynamic resources, governed cloud sandbox, asynchronous subagent delegation, durable system wake, and browser-verified parent/child projection implemented locally, 2026-08-19

## Purpose

BidPilot has two different AI execution modes. They solve different problems
and must not silently replace each other:

| Mode | Owner | Use it for |
| --- | --- | --- |
| Assistant Harness | Pi `AgentSession` (`services/pi-agent`) | A user conversation that decides with provider-native tool calls, reads structured observations, asks for missing input, and obtains approval for governed actions. |
| LangGraph workflow | API + worker + `ExecutionRun` | Long-running bid pipelines such as document ingestion, drafting, validation, review, and export. |

The public `/assistant/stream` endpoint enters the Pi runtime unconditionally.
It does not read an engine selector and cannot route a turn from user wording.
There is no automatic fallback to the retired Python loop: an unavailable Pi
sidecar produces a durable, diagnosable failure.

## Runtime inventory and migration boundary

| Entry | Production status | Boundary / removal plan |
| --- | --- | --- |
| `/assistant/stream` -> Pi sidecar | Supported public Assistant path | The only endpoint allowed to create a new `assistant_turn`; it projects Pi events onto the durable runtime trace. |
| `/assistant/attachments` | Supported companion API | Stages private attachment metadata; it cannot execute tools or start an agent loop. |
| `services/pi-agent` | Supported model loop | The official `@earendil-works/pi-coding-agent` `createAgentSession` runtime owns model turns, provider streaming, retry, compaction, queue lifecycle, parallel independent read tools, tool lifecycle, and bounded continuation. It has no database credentials. |
| `/internal/pi/tools/execute` | Internal bridge | Run-scoped token only. The existing BidPilot adapter remains authoritative for permissions, approvals, idempotency, audit and business writes. |
| `runtime/operator_graph.py` | Historical-run compatibility only | New public turns never create `langgraph_operator` runs. Retain only to finish/resume historical durable runs, then remove after **2026-09-30**. |
| `runtime/operator_adapter.py` | API compatibility facade | It preserves idempotency/replay plumbing while dispatching current turns to Pi. It is not a model loop and must not grow new behavior. |
| `services/api/app/agent/graph.py` | Historical ReAct compatibility only | No production route imports it; remove or move to an explicit replay package after migration gates pass. |
| Worker LangGraph graphs | Supported workflow engine | These are not Assistant routes. They execute durable `ExecutionRun` workflows for ingestion, drafting, validation and review resume. |

User text is data for the model, never server-side control flow. Production
code must not select a Skill, tool, retry policy, execution budget, or runtime
by substring/regex matching against the message. Pi selects tools through
provider-native tool calls; the API validates the structured call. The exact
project-name comparison used for destructive deletion is a typed confirmation
protocol, not an intent router.

Production configuration must set `DOCPILOT_ASSISTANT_ENGINE=pi` and provide
`DOCPILOT_PI_AGENT_URL`, `DOCPILOT_PI_TOOL_BRIDGE_URL`, and a dedicated
`DOCPILOT_PI_INTERNAL_SECRET` (the JWT secret is a local-development fallback
only). Historical development notes may refer to the older Python loop; this
inventory is the current authority.

## Harness turn lifecycle

1. The browser sends a new `client_request_id` for each submit.
2. The API resolves the project boundary, staged attachments, and a complete
   server-side or encrypted BYOK model configuration.
3. A `RuntimeRun(kind=assistant_turn, status=queued)` and a transactional
   `TaskOutboxEvent(task_name=worker.run_assistant_turn)` are created before
   any capability runs. The broker wake-up is best effort; Worker Beat
   rediscovers pending or expired outbox rows.
4. Worker claims the outbox delivery and invokes the API's signed internal
   execution entrypoint. The API loads the durable run context and starts Pi.
   Independent read-only calls may
   execute in parallel; mutating calls are sequential and each goes through the
   internal bridge. Campaign work uses the dedicated `run_section_campaign`
   tool rather than a burst of independent writes.
5. Every capability goes through authorization, policy, audit, and durable
   runtime events. The model never bypasses a product service.
6. The assistant response, terminal state, and public event summaries are
   persisted in PostgreSQL. During an active Worker-owned run, the API also
   publishes the same user-safe Pi frames through a run-scoped Redis live
   channel; the browser's initial SSE subscribes to that channel. PostgreSQL
   event replay is used only after reconnect, refresh, or a missed live
   channel, and closing the browser does not cancel the Worker task.

### Queue and reconnect contract

The browser must never be the owner of an assistant turn. The initial
`POST /assistant/stream` creates the durable run, subscribes to its ephemeral
Redis live channel before queue dispatch, and forwards Pi's current
`turn.started`, `thinking.*`, text deltas, tool lifecycle, and terminal frames
while the Worker executes. The Web client still keeps a per-run event cursor.
On a reconnect or reload it loads conversation messages and resumes from
`GET /runtime/runs/{run_id}/events?after_sequence=N`; this durable replay is a
recovery path, not the normal live rendering path. Terminal status is taken
from `RuntimeRun`, not inferred from a closed socket.

The Worker task is idempotent through the outbox delivery lease and the run
ID. A transient API/Pi transport failure releases the outbox row for retry;
the internal execution endpoint rejects a second active loop for the same
run. Pi remains unchanged: its AgentSession is created by the Worker-owned
execution attempt, while PostgreSQL `RuntimeRun`/`RuntimeEvent` remains the
cloud source of truth.

The web projection is conversation-scoped. Each browser tab keeps its selected
conversation in `sessionStorage`, while durable runs remain account/server
state. The provider keeps the active run and initial stream controller keyed by
conversation ID; changing conversations aborts only the old tab's projection
poller, never the Worker task. The composer cancellation control resolves the
run ID for the currently selected conversation, so two open conversations (or
two tabs) cannot share one stop target. Late replay events from an old
conversation are ignored by the visible projection.

### Pi integration boundary

Each Worker-delivered assistant turn creates a real Pi `AgentSession` with an
in-memory session manager for that attempt. This is deliberate: Pi owns the
active model/tool loop, while PostgreSQL owns the durable conversation,
business state, approvals, runtime events and cross-request recovery. Pi's
official `SessionManager.create/continueRecent/open` APIs can persist JSONL
sessions for local/desktop use, but they are not a cloud queue or a distributed
lease. Reusing those local files as a second source of truth would violate the
control-plane boundary and make horizontal deployment inconsistent.

The sidecar uses Pi's native `ModelRuntime`, `SettingsManager`, resource loader,
extension hooks, retry/compaction lifecycle and `agent_settled` terminal signal.
New turns do not call the retired Python ReAct loop or a locally reimplemented
model loop. The Pi session receives only server-defined BidPilot tools;
built-in host `bash`, `read`, `write`, `edit`, `grep`, `find`, and `ls` tools are
disabled in the cloud sidecar. Private deployments may add a separately
governed workspace companion, but tenant business writes must continue to pass
through the internal tool bridge.

### Profile memory provider boundary

Mem0 Platform is an optional personalization provider behind
`services/api/app/memory/mem0_provider.py`. It receives only bounded user and
assistant messages from successful turns and is instructed to retain low-risk
preferences such as language and response format. Tender facts, deadlines,
budgets, qualifications, source documents, tool payloads and credentials remain
in PostgreSQL-backed BidPilot records and are never delegated to the profile
provider.

The adapter follows Mem0's entity-scoping semantics: facts extracted from user
and assistant messages are stored under separate `user_id` and `agent_id`
records, so reads combine those scopes with `OR` while retaining `app_id` as a
tenant boundary. Account deletion removes the two entity scopes in separate
requests. `DOCPILOT_MEM0_APP_SCOPE=false` omits Platform-only `app_id` fields
for compatible OSS/self-hosted endpoints. The provider is fail-open for normal
assistant turns, but account deletion retries failures through the Worker.

Production enablement is intentionally explicit: both
`DOCPILOT_MEM0_ENABLED=true` and a server-side Mem0 key are required. The key
must be injected through the deployment secret store; it must not enter Git,
the browser, runtime events or logs.

### Trusted runtime resources and cloud sandbox

The API sends a server-authored resource and sandbox snapshot with every Pi
turn. Browser input cannot add extension paths, executable code, tools, or
Skills. The cloud sidecar accepts exactly one implemented profile:

- `profile=governed_cloud`
- `hostTools=disabled`
- `network=bridge_only`
- bounded tool input and model-observation sizes

Pi extensions run in-process and Pi does not provide an operating-system
sandbox. Therefore the sidecar loads only compiled, allowlisted inline
extension factories (`bidpilot-governance`, `bidpilot-skills` and
`bidpilot-subagents`). It rejects
filesystem extension paths, tenant JavaScript, duplicate resources, host-tool
names, direct model-selected network access, oversized input, and unknown
extension identifiers before a model-selected action can execute.

`bidpilot-governance` enforces the exact API-authorized capability set again at
Pi's native `tool_call` hook. `bidpilot-skills` uses Pi's native
`before_agent_start` hook to append Level-1 Skill metadata. Complete procedures
remain behind the governed `read_skill` capability. This preserves Pi's
progressive-disclosure model without giving the sidecar a general filesystem
reader or loading all business instructions into every prompt.

`approval_mode=full_access` / `Auto-run` is a business confirmation policy. It
does not change the sandbox profile, grant host access, reveal credentials, or
allow direct writes. The sidecar has no database or object-storage credentials;
every business observation and mutation crosses the short-lived, run-scoped API
bridge and is rechecked against tenant, policy, quota, approval, idempotency,
and audit rules.

A future `isolated_workspace` profile must run outside this process in a
container, VM, or microVM with an allowlisted mount, short-lived credentials,
network policy, CPU/memory/time quotas, output limits, and a separate audited
bridge. It must not be implemented as an in-process permission callback and is
not currently available.

### Pi-compatible subagents

Pi's official documentation intentionally leaves subagents and plan mode out
of the core; they are extension concerns. The first-party
`bidpilot-subagents` extension follows the official Pi example's three modes:

- `single`: one specialist profile and one self-contained task
- `parallel`: independent tasks queued at the same time
- `chain`: ordered tasks where each child depends on the previous child

The extension does not call `child_process`, read local agent files, or load an
arbitrary npm package. It sends one structured `spawn_subagents` call through
the existing run-scoped bridge. The API then creates a `RuntimeRun(kind=subagent)`
for every child, links it with `parent_run_id` and `trace_id`, writes the task
to the transactional outbox, and lets Worker execute it through a fresh Pi
sidecar session. Each child receives a new bridge token and the same tenant,
project, approval and audit boundary as its parent.

At delegation time the API freezes a versioned Pi execution contract containing
the audited tool schemas, trusted resource IDs and cloud sandbox settings. The
Worker consumes that snapshot instead of importing API-private runtime modules
or rebuilding a newer capability surface. Bridge JWT encoding and provider
protocol mappings live in the framework-neutral contracts package so API and
Worker share wire behavior without sharing service internals.

The current governance limits are explicit: at most eight child runs per
request, maximum depth three, maximum 32 child turns, and a 12 KiB delegated
prompt. A queued child is never reported as completed. Chain steps wait for a
successful predecessor and become a durable failure if that predecessor fails.
The model receives child run IDs, profiles, queue state and the resumable next
step; the browser can render the parent/child relationship from durable
runtime events instead of a synthetic progress card.

Delegation is always asynchronous at the HTTP bridge boundary. After the API
creates the durable children and outbox records, it immediately returns their
run IDs and queued state to Pi. The request handler never polls or joins child
results, because doing so would block sidecar streaming and prevent the browser
from observing the children while they run.

When a child reaches a terminal state, Worker writes a durable notification for
the exact parent conversation and source run. A signed, idempotent system-wake
task resumes Pi with that trusted terminal observation. This is a system event,
not a synthetic user message: no text such as "continue the background task" is
inserted into chat history and no browser-side keyword triggers a follow-up.
The browser may refresh an already open conversation after receiving the same
notification, but it is not responsible for continuing the model loop. Raw
child prompts, bridge tokens, private thinking and tool payloads are never
projected to the user. Chain workers wait for their dependency before claiming
the outbox lease, so a normal long-running predecessor cannot turn the successor
into a duplicate delivery.

### Browser execution projection

The browser projects durable runtime events; it does not infer product modes
from assistant prose, user wording, or tool-name substring matching. Ordinary
tool calls remain chronological execution rows. A Skill may additionally
declare a trusted `presentation` contract. The API copies that metadata and a
stable presentation-session ID onto related runtime events so the browser can
render one purpose-built runtime surface across multiple tool bursts.

`opportunity-deep-research`, for example, declares `presentation=deep_research`.
Its searches, source checks, evidence extraction and synthesis render as one
collapsible research runtime with stages and source progress, rather than a
flat wall of identical search rows. An ordinary standalone web search keeps the
standard row. Parallel subagents render as a paged parent/child viewer with
live child status and expandable public steps. Presentation metadata affects
only UI projection; it does not select a Skill, invoke a tool, or alter Pi's
decision loop.

Market packages such as `nicobailon/pi-subagents` and `tintinweb/pi-subagents`
were reviewed for interaction ideas (async delegation, parallel reviewers,
artifacts and steering). They are not installed into the cloud sidecar because
Pi extensions run in-process and third-party code would otherwise bypass
BidPilot's tenant and audit boundary. They remain reference implementations
for later private-deployment adapters after code and license review.

### Pi package admission policy

Pi packages can bundle extensions, Skills, prompt templates and themes from npm,
git or local paths. Pi's official package documentation also states that these
packages run with full system access. BidPilot therefore does not execute
`pi install` at request time and does not accept package identifiers from a
browser, tenant setting, model tool call or project document.

Cloud admission is a build-time registry in
`services/pi-agent/src/extensions/registry.ts`. Every executable entry records
an internal ID, contract version, deployment profile and first-party source.
The cloud runtime currently admits only governance, progressive Skill loading
and the audited subagent bridge. An npm or git package name is not an extension
ID and fails before a model turn starts.

Market review on 2026-08-18 produced this deployment classification:

| Capability | Representative references | Cloud decision | Private deployment decision |
| --- | --- | --- | --- |
| Subagents | official Pi example, `nicobailon/pi-subagents`, `@tintinweb/pi-subagents` | First-party governed equivalent implemented | Pinned package may be evaluated in an isolated workspace |
| Context pruning | `championswimmer/pi-context-prune` | Reimplement only against BidPilot's durable context policy | Candidate after retention/eval review |
| Interactive shell | `nicobailon/pi-interactive-shell` | Rejected from shared sidecar | Candidate only inside a workspace container/VM with quotas and approval |
| Browser control | `tianrendong/pi-chrome` | Rejected from shared sidecar | Candidate only with a dedicated browser profile and network policy |
| Local model provider | `huggingface/pi-llama` | Not a shared-cloud extension | Candidate adapter for enterprise on-premises inference |

Private-deployment admission must pin an exact npm version or git commit and
record license, source URL, checksum, approved resource paths, required host
capabilities and review status. Installation belongs in the isolated workspace
image build, never in the long-lived shared sidecar. Updating a package creates
a new reviewed image and execution-contract version; it cannot silently change
an in-flight run.

## Pi prompt and resource assembly

The Pi sidecar receives a small, composable system prompt rather than a
natural-language keyword router. The implementation reference is the
MIT-licensed `earendil-works/pi` coding-agent runtime. BidPilot adapts the
identity and product boundary but keeps the same architecture:

1. a stable assistant identity and a short set of general execution rules;
2. provider-native tool schemas supplied separately from the prose prompt;
3. trusted runtime/project context assembled near the current turn;
4. a small `<available_skills>` catalogue injected by a trusted Pi extension,
   with full instructions loaded on demand through the real `read_skill` tool.

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

### Browser event projection

The browser projects the durable event stream; it does not infer intent from
message text, capability names, or business keywords.

- Public narration and execution groups remain in their original chronology:
  `narration -> execution group -> narration -> execution group`. A Pi model
  turn may therefore produce more than one visual execution group when public
  narration occurs between tool bursts.
- `executionGroupId` is a frontend projection identity. It separates visual
  tool bursts without changing Pi turns or the runtime event schema. Persisted
  legacy traces without this identity fall back to `turn_id` once.
- Parent and child execution are linked only by durable `run_id` and
  `parent_run_id`. Child runs inherit the parent message and visual execution
  group, while retaining their own runtime identity for nested status and tool
  lifecycle rendering.
- Parallel child runs use a flat, paged subagent viewer inside the parent
  execution group. Each page exposes one child's current state and expandable
  public tool steps. It never exposes private reasoning, raw tool envelopes, or
  bridge credentials.
- Every execution level is collapsed by default. Running states remain visible
  in the summary row, and a live response retains a visible activity indicator
  while waiting for the next durable event.
- `created_at`, `type`, `public_summary`, and redacted `payload`

Core events are `run.started`, `plan.updated`, `capability.*`,
`approval.*`, `workflow.linked`, `message.*`, and terminal `run.*` events.
The legacy `assistant.*` SSE names are a compatibility projection only; new
backend work should produce durable runtime events first.

Pi event projection has three distinct audiences:

- Provider thinking content remains private model state. The sidecar emits only
  `thinking.started` / `thinking.completed`, never thinking token text.
- Normal assistant text deltas are public communication and stream immediately;
  they are not replaced with fixed progress copy generated by the frontend.
- Retry, compaction and queue events become ephemeral `assistant.runtime_state`
  updates. They may update the live busy state but must not create timeline
  cards or masquerade as user-facing reasoning.

The API accepts a Pi stream as successful only after an explicit terminal
event. A closed connection without `agent.completed` or `agent.failed` is a
runtime failure, preventing the browser from reporting a false completion or
remaining stuck indefinitely.

The browser restores transcript messages and all recent run-event streams in
parallel, merges them by durable time/sequence, and commits one conversation
snapshot. This prevents a transcript from rendering first and execution
history jumping in later. Timeline groups are collapsed by default at every
level and are never opened or closed by incoming events; only the user changes
disclosure state. Running/thinking aggregate labels may use a restrained
motion treatment, while completed or failed labels remain static.

### Memory boundary

Memory is split by lifecycle and authority:

| Layer | Owner | Purpose |
| --- | --- | --- |
| Pi `AgentSession` | Pi sidecar, in memory | One Worker attempt's active model/tool context, queue, retry and compaction state |
| Conversation/runtime | PostgreSQL | Exact ChatMessage history, RuntimeRun/Event, approvals, waits and recovery |
| Profile memory | Optional Mem0 Platform adapter | Low-risk user preferences and communication style across conversations |
| Business memory | BidPilot PostgreSQL `MemoryRecord` | Evidence-backed tender facts, requirements, risks, decisions and citations |

Mem0 is enabled only by explicit server configuration and is called through the
official `mem0ai` SDK. API recalls profiles before a Pi turn; Worker captures a
bounded user/assistant exchange asynchronously after a successful turn. Calls
are scoped with the current `user_id`, `agent_id` and organization `app_id`.
The local `Mem0ProfileSync` ledger makes capture idempotent without storing
provider payloads or conversation text. Mem0 failures are fail-open for the
assistant path. Account deletion schedules a scoped provider `delete_all`.

Mem0 never receives tender files, evidence payloads, hidden model reasoning,
credentials or tool envelopes, and it cannot authorize or mutate BidPilot
business state. A private deployment may replace the adapter with self-hosted
Mem0 OSS; the Pi and control-plane contracts remain unchanged.

### Cross-session design reference

Claude Code's public memory design separates user-authored instructions from
agent-authored learnings: `CLAUDE.md` is loaded every session, while an
auto-memory directory keeps a small `MEMORY.md` index and topic files loaded on
demand. Its automatic memory is machine-local, so it is not a cloud durability
model. BidPilot maps the same idea to server primitives: project/org policy and
skills are authoritative instructions; PostgreSQL ChatMessage/RuntimeRun are
exact cross-session history; Mem0 is the searchable user-profile layer; and
BidPilot MemoryRecord is the reviewed business knowledge layer. We do not copy
local Markdown memory files into the shared cloud control plane.

Reference: [Claude Code memory documentation](https://code.claude.com/docs/en/memory).

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
- Pi `AgentSession` terminal delivery after retry/compaction settles
- private provider thinking never entering transcript or public event payloads
- independent read tools overlapping while mutating tools remain sequential

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
frontmatter (`name`, `description`). The API validates this server-owned
registry, sends Level-1 metadata only, and omits the older prompt-assembly Skill
block for Pi turns. The trusted `bidpilot-skills` extension appends the catalogue
at Pi's `before_agent_start` boundary. The model selects a Skill by meaning and
calls the server-owned `read_skill(name)` tool to load its Level-2 body. The API
accepts only an exact allowlisted Skill name. Product code must not route Skills
by matching user-message keywords.

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
