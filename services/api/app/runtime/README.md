# Runtime Ownership

`app.runtime` is the API-side control plane for assistant runs. It owns the
durable run/event/approval contract and the Pi integration boundary.

## Production path

```text
app.assistant.router
  -> app.runtime.operator_adapter (API compatibility facade)
  -> app.runtime.pi_adapter
  -> services/pi-agent
  -> app.runtime.pi_bridge
  -> app.runtime.registry / policy / service
  -> PostgreSQL RuntimeRun / RuntimeAction / RuntimeApproval / RuntimeEvent
```

The Pi path uses the official Pi AgentSession in `services/pi-agent` for the
provider/model/tool loop. `app.runtime.pi_adapter` assembles trusted context
and projects the sidecar stream; `app.runtime.pi_bridge` sends each structured
tool call back to the API for authorization, approval, audit and business
execution. `app.runtime.model` and `app.runtime.conversation` remain API-side
provider/context helpers, not alternate agent loops. New runtime code must not
import `app.agent` or the legacy Operator graph directly.

## Compatibility boundary

The following modules are retained for replay, migration and historical test
coverage only. They are not an automatic fallback for a new Pi run:

- `assistant_adapter.py` (legacy SSE/event compatibility projection)
- `harness_loop.py`
- `harness_host.py`
- `operator_graph.py`
- the legacy branch of `operator_adapter.py`
- `app.agent.graph` and the `app.agent` namespace

Legacy code may be called only by an explicit replay/evaluation path. A new
business capability belongs in `registry.py`, `policy.py`, `service.py` and
the signed Pi bridge; it must not be added to the old loop.

The compatibility event renderer is still shared while the public SSE
contract is being migrated, but it is side-effect free at import time. The
retired `AssistantRuntime` instance is created only when an explicit legacy
replay function calls it; importing the Pi adapter does not start the old
classifier or its loop.

## Dependency direction

```text
apps/web                -> public REST/SSE contracts
feature routers/services -> runtime control plane -> contracts + domain services
pi_adapter              -> services/pi-agent (wire protocol only)
pi_bridge               -> runtime registry/policy/service + domain executor
services/pi-agent       -> Pi packages + compiled trusted extensions
legacy replay           -> compatibility modules (one-way, lazy imports)
```

`services/pi-agent` must not import this Python package, SQLAlchemy models,
API routers, or tenant credentials. The API must not embed a second model loop
in a feature service. Long-running ingestion/drafting/review/export execution
belongs to `services/worker` and its LangGraph graphs.

`RuntimeRun` and `RuntimeEvent` remain the source of truth. SSE is only a
projection of persisted events, and the sidecar never receives database
credentials or a SQLAlchemy session.

## Migration rule

Do not delete the compatibility modules until historical replay and runtime
evaluation fixtures have moved to the Pi contracts. The migration work should
remove imports first, then move tests, then remove files in a separately
reviewed change.
