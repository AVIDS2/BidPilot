# BidPilot Unified Agent Runtime v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Assistant turns and workflow operations share a durable, policy-governed runtime contract with replayable events and idempotent approval/recovery behavior.

**Architecture:** Add a product-owned PostgreSQL runtime control plane (`RuntimeRun`, `RuntimeEvent`, `RuntimeAction`, `RuntimeApproval`) while retaining `ExecutionRun` as the domain record for a background workflow. Use one capability registry and policy evaluator for deterministic and LangGraph operator adapters; worker nodes publish product events instead of the API scraping LangGraph checkpoint tables.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, PostgreSQL, LangGraph 1.2, Celery, React, SSE, pytest, Vitest.

**Reference design:** `docs/superpowers/specs/2026-07-14-bidpilot-unified-runtime-v1-design.md`

---

## File Map

- `packages/contracts/runtime.py`: framework-neutral runtime enums and Pydantic event/approval contracts.
- `packages/contracts/models.py`: SQLAlchemy runtime control-plane models.
- `services/api/alembic/versions/e8f9a0b1c2d3_add_runtime_control_plane.py`: additive schema migration and indexes.
- `services/api/app/runtime/schemas.py`: API-facing request/read schemas.
- `services/api/app/runtime/repository.py`: database reads/writes with sequence allocation.
- `services/api/app/runtime/events.py`: redacted, ordered event publisher and replay reader.
- `services/api/app/runtime/policy.py`: product policy decision contract.
- `services/api/app/runtime/registry.py`: capability definitions, validators, formatters, and executor bindings.
- `services/api/app/runtime/service.py`: run lifecycle, idempotency, approvals, retries, and cancellation.
- `services/api/app/runtime/router.py`: run detail, event replay, approval, cancel, and retry endpoints.
- `services/api/app/runtime/operator_graph.py`: bounded LangGraph Assistant operator adapter.
- `services/api/app/assistant/router.py`: delegates new Assistant turns to the runtime service.
- `services/api/app/assistant/service.py`: temporary deterministic adapter only; no longer owns its own audit/approval protocol.
- `services/api/app/agent/{graph.py,streaming.py,tools.py,policy.py}`: migrate or retire duplicated policy/tool logic in favor of runtime adapters.
- `services/worker/app/runtime/events.py`: worker-safe runtime event publisher.
- `services/worker/app/graph/{builder.py,state.py}` and `services/worker/app/graph/nodes/*.py`: emit product runtime progress and enforce explicit checkpointer mode.
- `services/api/app/drafting/streaming.py`: read persisted runtime events rather than checkpoint internals.
- `apps/web/src/lib/ai-assistant-store.tsx`: consume ordered runtime events and reconnect with sequence cursors.
- `apps/web/src/components/ai-assistant/*`: render typed public events, approvals, and retry/cancel state.
- `services/api/tests/runtime/*`: contract, policy, idempotency, event, approval, and replay tests.
- `services/api/tests/assistant/*`, `services/api/tests/drafting/*`, `apps/web/src/components/ai-assistant/*.test.tsx`: compatibility and user-flow tests.

## Task 1: Define the Stable Runtime Contract

**Files:**
- Create: `packages/contracts/runtime.py`
- Modify: `packages/contracts/__init__.py`
- Test: `services/api/tests/runtime/test_contracts.py`

- [x] **Step 1: Write failing contract tests for events, lifecycle states, and a redacted public payload.**

```python
def test_runtime_event_requires_a_monotonic_sequence_and_public_summary() -> None:
    event = RuntimeEventRecord(
        run_id="run-1",
        sequence=2,
        type=RuntimeEventType.CAPABILITY_SUCCEEDED,
        public_summary="已找到 2 个项目。",
        payload={"count": 2},
    )
    assert event.sequence == 2
    assert event.payload["count"] == 2


def test_runtime_approval_cannot_be_created_for_a_terminal_action() -> None:
    with pytest.raises(ValidationError):
        RuntimeApprovalDecision(action_status="succeeded", status="pending")
```

- [x] **Step 2: Run the contract test before implementation.**

```powershell
$env:DOCPILOT_DATABASE_URL='postgresql+psycopg://docpilot:docpilot@localhost:5433/docpilot_migration_test'
uv run --directory services/api pytest tests/runtime/test_contracts.py -q
```

Expected: import failure because the runtime contract does not exist.

- [x] **Step 3: Add exact shared enums and Pydantic models.**

```python
class RuntimeRunKind(StrEnum):
    ASSISTANT_TURN = "assistant_turn"
    WORKFLOW_BRIDGE = "workflow_bridge"
    SYSTEM_RECOVERY = "system_recovery"


class RuntimeRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class RuntimeEventType(StrEnum):
    RUN_STARTED = "run.started"
    PLAN_PROPOSED = "plan.proposed"
    CAPABILITY_STARTED = "capability.started"
    CAPABILITY_PROGRESSED = "capability.progressed"
    CAPABILITY_SUCCEEDED = "capability.succeeded"
    CAPABILITY_FAILED = "capability.failed"
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_RESOLVED = "approval.resolved"
    WORKFLOW_LINKED = "workflow.linked"
    MESSAGE_COMPLETED = "message.completed"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    RUN_CANCELLED = "run.cancelled"
```

Include `RuntimeContext`, `RuntimeEventRecord`, `RuntimePolicyDecision`, `RuntimeActionStatus`, and `RuntimeApprovalStatus`. Use `extra="forbid"` for persisted public event payload models.

- [x] **Step 4: Re-run contract tests.**

Expected: `2 passed` or more, with no API/provider dependency.

## Task 2: Add the Additive Runtime Control-Plane Migration

**Files:**
- Modify: `packages/contracts/models.py`
- Modify: `services/api/app/models.py`
- Create: `services/api/alembic/versions/e8f9a0b1c2d3_add_runtime_control_plane.py`
- Test: `services/api/tests/runtime/test_migration.py`

- [x] **Step 1: Write a migration test that upgrades from `d7e8f9a0b1c2` and asserts all four runtime tables and unique keys.**

```python
def test_runtime_control_plane_migration_creates_idempotent_tables(migration_database) -> None:
    upgrade(migration_database, "e8f9a0b1c2d3")
    assert has_columns(migration_database, "runtime_run", {"trace_id", "idempotency_key", "policy_snapshot_json"})
    assert has_unique_index(migration_database, "runtime_event", ("run_id", "sequence"))
    assert has_unique_index(migration_database, "runtime_action", ("run_id", "action_key"))
    assert has_unique_index(migration_database, "runtime_approval", ("action_id",))
```

- [x] **Step 2: Run it and verify failure before the migration is present.**

```powershell
uv run --directory services/api pytest tests/runtime/test_migration.py -q
```

- [x] **Step 3: Add models with explicit ownership and foreign keys.**

`RuntimeRun` fields: id, kind, status, org_id, user_id, nullable project_id, nullable conversation_id, nullable parent_run_id, nullable execution_run_id, engine, trace_id, nullable idempotency_key, provider/model/reasoning metadata, policy snapshot, input/result/error envelopes, and lifecycle timestamps.

`RuntimeEvent` fields: id, run_id, sequence, event type, public summary, redacted payload JSON, schema version, created_at.

`RuntimeAction` fields: id, run_id, action_key, capability name, status, redacted arguments/result, policy decision, error code/message, created/completed timestamps.

`RuntimeApproval` fields: id, action_id, requesting user/org, status, redacted payload, expires/resolved timestamps.

The migration is additive, uses indexes for `(org_id, status, created_at)`, `(run_id, sequence)`, and unique action/idempotency keys, and never modifies legacy assistant tables.

- [x] **Step 4: Upgrade a disposable migration database, downgrade one revision, and upgrade again.**

```powershell
$env:DOCPILOT_DATABASE_URL='postgresql+psycopg://docpilot:docpilot@localhost:5433/docpilot_migration_test'
uv run --directory services/api alembic upgrade head
uv run --directory services/api pytest tests/runtime/test_migration.py -q
```

Expected: migration test passes and `alembic current` reports the new head.

## Task 3: Persist Ordered Events and Reconnect Safely

**Files:**
- Create: `services/api/app/runtime/{__init__.py,repository.py,events.py,schemas.py,router.py}`
- Modify: `services/api/app/main.py`
- Test: `services/api/tests/runtime/test_events.py`

- [x] **Step 1: Write failing tests for ordered append, safe replay, and non-member denial.**

```python
def test_publish_allocates_contiguous_sequence_per_run(db, runtime_run) -> None:
    first = publish_event(db, runtime_run.id, RuntimeEventType.RUN_STARTED, "任务已开始")
    second = publish_event(db, runtime_run.id, RuntimeEventType.CAPABILITY_STARTED, "正在搜索项目")
    assert (first.sequence, second.sequence) == (1, 2)


def test_event_replay_hides_run_from_non_member(client, other_user, runtime_run) -> None:
    response = client.get(f"/runtime/runs/{runtime_run.id}/events", headers=auth(other_user))
    assert response.status_code == 404
```

- [x] **Step 2: Implement a publisher that locks the run row while allocating sequence numbers.**

```python
def publish_event(db: Session, run: RuntimeRun, event: RuntimeEventDraft) -> RuntimeEvent:
    locked = db.scalar(select(RuntimeRun).where(RuntimeRun.id == run.id).with_for_update())
    sequence = repository.next_event_sequence(db, locked.id)
    row = RuntimeEvent(run_id=locked.id, sequence=sequence, ...)
    db.add(row)
    db.commit()
    return row
```

Always call shared redaction before persistence. The payload may contain renderer fields but no model prompt, provider object, raw exception, or credential.

- [x] **Step 3: Expose `GET /runtime/runs/{run_id}` and `GET /runtime/runs/{run_id}/events?after_sequence=N`.**

The event endpoint returns a finite replay first. A later live fan-out optimization may use Redis pub/sub, but v1 must return the durable PostgreSQL sequence correctly even after reconnect.

- [x] **Step 4: Run event tests and API OpenAPI smoke checks.**

```powershell
uv run --directory services/api pytest tests/runtime/test_events.py tests/test_openapi_smoke.py -q
```

Expected: event ordering, replay cursor, redaction, and tenant boundaries are covered.

## Task 4: Create One Capability Registry and Policy Evaluator

**Files:**
- Create: `services/api/app/runtime/{registry.py,policy.py,capabilities.py}`
- Modify: `services/api/app/agent/policy.py`
- Modify: `services/api/app/assistant/tools.py`
- Modify: `services/api/app/agent/tools.py`
- Test: `services/api/tests/runtime/test_policy_and_registry.py`

- [x] **Step 1: Write failing parameterized tests for every existing public capability.**

```python
@pytest.mark.parametrize(
    ("capability", "risk", "approval_in_risky_only"),
    [
        ("search_projects", "read", False),
        ("get_readiness_summary", "read", False),
        ("create_project", "low_risk_write", True),
        ("start_draft_section", "costing", True),
        ("delete_project", "destructive", True),
    ],
)
def test_registry_policy_metadata(capability, risk, approval_in_risky_only):
    definition = registry.get(capability)
    assert definition.risk_level == risk
    assert evaluate_policy(definition, approval_mode="risky_only").requires_approval is approval_in_risky_only
```

- [x] **Step 2: Add one `CapabilityDefinition` per supported capability.**

The first registry includes: search/list project data, readiness summary/gaps/source lookup, navigation, project creation, deliverable creation, drafting/redrafting, retry, export, attachment import bridge, and delete. Each executor delegates to the existing service command/query and returns a typed result object.

- [x] **Step 3: Replace duplicated `TOOL_POLICIES` and direct execution dispatch with registry lookups.**

Do not remove legacy names until every caller has migrated. Keep small compatibility functions that call `registry.get(name)` so tests and old routes retain stable behavior during the rollout.

- [x] **Step 4: Ensure public formatters own all user-facing summaries.**

```python
assert format_public_result("search_projects", {"count": 2}).summary == "找到 2 个项目。"
assert "search_projects" not in format_public_result("search_projects", {"count": 2}).summary
```

- [x] **Step 5: Run policy, assistant, and access suites.**

```powershell
uv run --directory services/api pytest tests/runtime/test_policy_and_registry.py tests/assistant tests/access -q
```

Expected: no raw capability names or raw payload fields are required by the product event formatter.

## Task 5: Add Idempotent Actions and Generic Approvals

**Files:**
- Create: `services/api/app/runtime/service.py`
- Modify: `services/api/app/runtime/{policy.py,registry.py,router.py}`
- Test: `services/api/tests/runtime/test_actions_and_approvals.py`

- [x] **Step 1: Write tests for one action per idempotency key, approval replay denial, rejection, expiry, and full-access hard-delete confirmation.**

```python
def test_resumed_action_executes_create_project_once(db, context):
    first = execute_capability(db, context, "create_project", {"name": "A"}, action_key="tool-1")
    second = execute_capability(db, context, "create_project", {"name": "A"}, action_key="tool-1")
    assert first.action_id == second.action_id
    assert project_count(db, "A") == 1


def test_expired_approval_cannot_be_replayed(client, pending_approval):
    expire(pending_approval)
    response = client.post(f"/runtime/approvals/{pending_approval.id}/resolve", json={"decision": "approve"})
    assert response.status_code == 409
```

- [x] **Step 2: Implement `execute_capability` as the single effect boundary.**

It must resolve authorization/resource scope, evaluate policy, create/get the action by `(run_id, action_key)`, append a `capability.started` event, request approval or call the executor, then append exactly one terminal action event. A committed successful action returns its stored result instead of repeating the domain command.

- [x] **Step 3: Implement generic approval routes.**

```http
POST /runtime/approvals/{approval_id}/resolve
{"decision":"approve"}

POST /runtime/approvals/{approval_id}/resolve
{"decision":"edit","arguments":{"name":"Corrected name"}}

POST /runtime/approvals/{approval_id}/resolve
{"decision":"reject","reason":"Wait for manager review"}
```

Only approval-compatible capabilities permit `edit`; destructive actions accept approve/reject only. Approval resolution appends `approval.resolved` before re-entering the action executor.

- [x] **Step 4: Run focused tests.**

```powershell
uv run --directory services/api pytest tests/runtime/test_actions_and_approvals.py -q
```

Expected: action and approval records are usable independently of either Agent engine.

## Task 6: Build the Bounded LangGraph Operator Adapter

**Files:**
- Create: `services/api/app/runtime/operator_graph.py`
- Modify: `services/api/app/assistant/router.py`
- Modify: `services/api/app/assistant/runtime.py`
- Modify: `services/api/app/agent/{graph.py,streaming.py}`
- Test: `services/api/tests/runtime/test_operator_adapters.py`

- [x] **Step 1: Write adapter parity tests with a fake model.**

```python
@pytest.mark.asyncio
async def test_deterministic_and_langgraph_adapters_emit_same_safe_read_contract(runtime_context):
    expected = ["run.started", "capability.started", "capability.succeeded", "message.completed", "run.completed"]
    assert await collect_event_types(run_deterministic(runtime_context, "查看项目")) == expected
    assert await collect_event_types(run_operator_graph(runtime_context, FakeToolCallingModel())) == expected
```

- [x] **Step 2: Implement an explicit graph with bounded model/tool loop.**

Use `StateGraph`, a `messages` reducer, `max_capability_calls`, a model node, and a policy-gated tool node. The tool node calls `execute_capability`. On required approval it emits an event and calls `interrupt(public_approval_payload)`. Resume uses `Command(resume=...)` and the runtime run id as `thread_id`.

Do not use the old agent wrapper as the authoritative executor. Do not emit model reasoning; persist only an optional concise `plan.proposed` created by the adapter.

- [x] **Step 3: Make the deterministic adapter call the same registry/service.**

The deterministic classifier may choose a capability or request a field, but must not execute a separate tool/audit/approval path. Preserve it under `DOCPILOT_ASSISTANT_ENGINE=deterministic` for tests and local no-provider development.

- [x] **Step 4: Change the Assistant route to create a `RuntimeRun` and translate runtime events to compatibility SSE.**

Continue emitting existing `assistant.*` SSE names during the frontend migration. The mapping must be a thin renderer over typed runtime events, not a second lifecycle implementation.

- [x] **Step 5: Run operator, assistant, and secret-redaction tests.**

```powershell
uv run --directory services/api pytest tests/runtime/test_operator_adapters.py tests/assistant tests/security -q
```

Expected: provider-free deterministic tests pass, LangGraph interrupts resume through the generic approval service, and safe reads show tool state before prose completion.

## Task 7: Bridge Worker Workflows to Runtime Events

**Files:**
- Create: `services/worker/app/runtime/events.py`
- Modify: `services/worker/app/graph/{builder.py,state.py}`
- Modify: `services/worker/app/graph/nodes/{rfp_parser.py,knowledge_retriever.py,section_drafter.py,quality_reviewer.py,human_approval.py,persist_result.py}`
- Modify: `services/api/app/drafting/{service.py,streaming.py}`
- Test: `services/api/tests/runtime/test_workflow_bridge.py`

- [x] **Step 1: Write a worker bridge test that forbids checkpoint-table reads.**

```python
def test_workflow_node_publishes_runtime_events_without_checkpoint_query(monkeypatch, runtime_run):
    monkeypatch.setattr("app.runtime.events.publish_event", recorder)
    run_section_drafter_fixture(runtime_run)
    assert [event.type for event in recorder.events] == [
        RuntimeEventType.CAPABILITY_STARTED,
        RuntimeEventType.CAPABILITY_SUCCEEDED,
    ]
```

- [x] **Step 2: Make workflow start create a linked `RuntimeRun(kind=workflow_bridge)`.**

The drafting command links the parent Assistant run when present, otherwise creates a standalone bridge run. It emits `workflow.linked` and passes the bridge run id in graph state. The domain `ExecutionRun` remains the durable worker job id.

- [x] **Step 3: Publish real node lifecycle events from worker nodes.**

Each node appends start, bounded progress, success/failure, and approval-pause events via the shared contract. `human_approval_node` keeps `interrupt()` and must publish its approval request before pausing. `PostgresSaver` failure in production records a run failure; only explicit local/test mode may use memory.

- [x] **Step 4: Replace `drafting/streaming.py` checkpoint polling with runtime event replay.**

The stream returns node progress from `RuntimeEvent` records. It may retain a short compatibility mapper for existing `node_started`, `node_completed`, and `graph_completed` client event names until the frontend uses the generic feed.

- [x] **Step 5: Run worker/API bridge tests and graph validation.**

```powershell
uv run --directory services/api pytest tests/runtime/test_workflow_bridge.py tests/drafting -q
uv run python scripts/validate_agent_graph.py services/worker/app/graph/builder.py:get_graph
```

Expected: workflow progress survives reconnect without querying LangGraph internal tables.

## Task 8: Upgrade the Agent UI to the Typed Event Feed

**Files:**
- Modify: `apps/web/src/lib/ai-assistant-store.tsx`
- Modify: `apps/web/src/components/ai-assistant/{assistant-execution-card.tsx,assistant-workflow-card.tsx,AIAssistantPanel.tsx,assistant-tool-metadata.ts}`
- Create: `apps/web/src/lib/runtime-events.ts`
- Test: `apps/web/src/lib/runtime-events.test.ts`
- Test: `apps/web/src/components/ai-assistant/AIAssistantPanel.test.tsx`

- [x] **Step 1: Write a reducer test for ordered, replayed events.**

```ts
it("does not duplicate an action after replay", () => {
  const state = reduceEvents([], [started(1), succeeded(2), succeeded(2)]);
  expect(state).toHaveLength(2);
  expect(state.at(-1)?.sequence).toBe(2);
});
```

- [x] **Step 2: Convert runtime events into user-facing timeline entries.**

Map `capability.*` to localized labels supplied by registry metadata. Render only public summaries. Group completed adjacent actions into an expandable Codex/Claude-style execution row; show a pending approval in the chronological location where it paused.

- [x] **Step 3: Add reconnect behavior.**

When a panel reopens or SSE reconnects, request events after the last sequence. Token deltas remain ephemeral; completed message and action events recover from the API.

- [x] **Step 4: Add cancellation/retry controls only when the matching runtime policy says they are available.**

The UI cannot invent a cancel state. It submits the generic runtime route and waits for the persisted event result. Workflow cancellation is available only for a linked `workflow_bridge` run and stops at a Worker-safe graph boundary. Retry now creates a child `ExecutionRun` and child workflow bridge with fresh quota and audit evidence; it remains absent from the visible panel until the project-history retry UX and permissions copy are designed.

- [ ] **Step 5: Run component tests, full web test suite, build, and desktop/mobile Playwright smoke tests.**

```powershell
pnpm --filter @docpilot/web test -- --run
pnpm --filter @docpilot/web build
```

Expected: no raw tool payload, no action appears after final answer, and narrow layouts preserve event/approval/input visibility.

## Task 9: Release Evidence and Legacy Retirement Decision

**Files:**
- Modify: `docs/adr/0001-core-technology-stack.md` only if an engine dependency decision changes
- Create: `docs/adr/0005-unified-agent-runtime.md`
- Create: `docs/dev-log/2026-07-14-unified-agent-runtime.md`
- Modify: `progress.txt`
- Test: `services/api/tests/runtime/test_release_contract.py`

- [ ] **Step 1: Write a release-contract test covering one safe read, one approval, one interrupted resume, one workflow bridge, one cancellation, and cross-tenant replay denial.**

- [ ] **Step 2: Run full verification on an Alembic-migrated test database.**

```powershell
$env:DOCPILOT_DATABASE_URL='postgresql+psycopg://docpilot:docpilot@localhost:5433/docpilot_migration_test'
uv run --directory services/api alembic upgrade head
uv run --directory services/api pytest -q
pnpm --filter @docpilot/web test -- --run
pnpm --filter @docpilot/web build
git diff --check
```

- [ ] **Step 3: Perform an independent read-only review of the runtime diff.**

Review questions:

1. Can either engine bypass authorization, policy, or approval persistence?
2. Can a resumed node duplicate a domain side effect?
3. Do any event/audit/SSE fields expose raw provider payloads or credentials?
4. Is a worker failure explicit, and does production avoid silent memory fallback?
5. Does the UI derive state only from typed runtime events?

- [ ] **Step 4: Update ADR, delivery log, progress, and known limitations.**

Document the exact rollout status. Do not claim runtime unification complete until both adapters and the worker bridge pass the same contract tests.

## Plan Self-Review

- Product-runtime scope is covered by Tasks 1–7; UI and release evidence are Tasks 8–9.
- The plan intentionally does not add long-term memory, graph database, generic MCP, arbitrary network access, or a generic workflow builder.
- All effectful behavior has an idempotency boundary in Task 5 before the LangGraph adapter is allowed to execute it in Task 6.
- The worker is migrated to product events only after the generic event store exists, so current workflow functionality remains available during the rollout.
- Contract, migration, authorization, idempotency, approval, event ordering, replay, worker bridge, UI, and full verification each have explicit test tasks.
