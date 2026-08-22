# Repository Blueprint

## Goal

Provide the canonical repository structure and dependency direction for clean
development. This map describes the current modular monolith: deployable
runtime units are separate, while business domains stay in the API/Worker
applications until independent scaling or ownership justifies extraction.

## Top-level target

```text
docpilot/
  apps/
    web/
  services/
    api/
    worker/
    pi-agent/
  packages/
    contracts/
  scripts/
  docs/
```

## Frontend target

```text
apps/web/
  src/
    app.tsx
    features/
      agent/
        state/                 # Agent client state
        runtime/               # RuntimeEvent projection and transcript mapping
        components/            # active Agent UI
        legacy/                # quarantined assistant-ui experiment
      workbench/               # authenticated shell and product screens
    components/
      ui/                      # shadcn primitives
    lib/
    hooks/
  .storybook/
```

## API target

```text
services/api/
  app/
    core/
    db/
    projects/
    bundles/
    documents/
    requirements/
    retrieval/
    execution/
    deliverables/
    review/
    audit/
    auth/
    providers/
    runtime/
      pi_adapter.py       # API-to-Pi orchestration and public SSE projection
      pi_bridge.py        # signed, run-scoped capability bridge
      registry.py         # capability schemas and governance metadata
      service.py          # durable RuntimeRun/RuntimeEvent/approval services
  tests/
  alembic/
```

## Worker target

```text
services/worker/
  app/
    tasks/
    execution/
    adapters/
    services/
  tests/

services/pi-agent/
  src/
    runtime.ts            # Pi AgentSession/model/tool loop
    server.ts             # internal NDJSON sidecar boundary
    extensions/           # compiled, allowlisted Pi extensions
    contracts.ts          # sidecar wire contracts
  Dockerfile
  package.json
```

## Contracts target

```text
packages/contracts/
  src/
    api/
    events/
    ids/
    enums/
```

## Rules

- do not create folders only for hypothetical future abstractions
- prefer feature- or domain-oriented grouping over generic utility sprawl
- keep shared code truly shared; otherwise leave it in the owning feature
- when in doubt, align new files to this blueprint and the corresponding application architecture docs

## Ownership and dependency direction

```text
apps/web
  -> public REST/SSE contracts
services/api
  -> packages/contracts
  -> domain services / repositories / adapters
  -> signed bridge to services/pi-agent
services/worker
  -> packages/contracts
  -> domain services / repositories / execution adapters
services/pi-agent
  -> packages/contracts (wire types only)
  -> provider-native Pi packages and compiled trusted extensions
```

The following dependencies are forbidden:

- Web importing Python modules, ORM models, Worker internals, or Pi packages.
- Pi sidecar connecting directly to PostgreSQL, Redis, MinIO, or a tenant
  provider key. Business reads and writes must cross the API bridge.
- API routers importing LangGraph nodes or writing domain tables directly.
- Worker tasks importing HTTP routers or using browser state as a run source.
- Domain services depending on prompt text, runtime memory, or frontend state.
- New code importing the historical Python Harness/ReAct/operator loop.
- Web routes importing the quarantined Agent `legacy/` surface.
- Runtime event projection living in generic `lib/`; it belongs to the Agent
  feature boundary.

## Legacy quarantine

The repository contains older runtime modules under
`services/api/app/runtime/` (for example `harness_loop.py`, `harness_host.py`,
`operator_adapter.py`, and `operator_graph.py`). They are retained so already
persisted runs and migration tests can be replayed. They must be treated as a
compatibility boundary: no new route, tool, prompt, UI behavior, or deployment
default may depend on them. When the historical replay window closes, move the
remaining files into an explicit `legacy/` package and delete only after the
replay and migration gates pass.
