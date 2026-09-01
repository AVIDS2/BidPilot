# Local Development Workflow

## Goal

Give future implementation sessions a predictable path from first clone to validated local change.

## Development baseline

Local development should support:

- web UI iteration
- API development
- worker development
- database migrations
- parser and drafting job debugging

Local assumptions are defined in:

- `docs/development/local-environment-baseline.md`

## Expected local services

- API service
- Pi sidecar
- web service
- PostgreSQL, Redis, MinIO and Worker only when the task requires them and an
  approved host/isolated instance is already available

## Default workflow

1. `conda activate llm` when Python work is required.
2. Start the direct-process local API with an ignored local environment file.
3. Start the local Pi sidecar on `127.0.0.1:8787`.
4. Start the Next web app on `127.0.0.1:3300` with
   `DOCPILOT_API_URL=http://127.0.0.1:8000`.
   Set `DOCPILOT_LOCAL_DIRECT_ASSISTANT=true` when Redis/Worker are not
   available and a local Pi turn must be exercised.
5. Start Worker/Redis/MinIO only for a task that needs asynchronous or
   object-storage behavior and only after approved local dependencies exist.
6. Run smoke checks against loopback services.

## Feature workflow

1. read the relevant spec and phase plan
2. add or update tests first when behavior changes
3. implement the narrowest useful slice
4. verify API, worker, and web behavior as relevant
5. update docs if scope, architecture, or operations changed

## Recommended branch of work

### Product behavior changes

Read:

- `docs/superpowers/specs/2026-04-18-docpilot-design.md`
- relevant phase plan
- `docs/product/frontend-experience-principles.md` for meaningful frontend UX changes
- `docs/product/source-data-strategy.md` for ingestion or source-material behavior changes

### Architecture or dependency changes

Read:

- `docs/adr/0001-core-technology-stack.md`
- `docs/adr/0002-workflow-and-execution-architecture.md` for workflow or queue decisions
- `docs/development/final-technology-baseline.md` for the accepted default stack
- relevant architecture doc
- `docs/architecture/frontend-application-architecture.md` for frontend structure changes
- `docs/architecture/backend-application-architecture.md` for backend structure changes
- `docs/architecture/repository-blueprint.md` for repo organization changes
- `docs/architecture/document-ingestion-and-format-strategy.md` for parser or file-format changes
- `docs/architecture/normalized-document-schema.md` for parsed structure or chunk/evidence changes
- `docs/architecture/execution-and-workflow-architecture.md` for execution lifecycle or state-machine changes
- `docs/development/configuration-and-secrets.md` when config or env behavior changes

### Release or incident changes

Read:

- `docs/ops/deployment-and-runbook.md`
- `docs/ops/observability-and-sre.md`
- `docs/ops/environment-matrix.md`

## Local verification minimum

Before considering a change complete:

- run relevant unit tests
- run one API smoke path
- run one worker smoke path when async logic changes
- verify the web route or feature you changed

## Seed data guidance

- keep one small demo project bundle for repeatable local demos
- separate development fixtures from benchmark or large-scale test data
- keep sample documents safe for public demonstration
- align repeatable end-to-end fixtures with `docs/quality/acceptance-scenarios.md`

## Local stability rules

- local mode must not require a cloud-only managed service
- local env vars should default to development-safe values
- local queue and object storage should mimic production contracts closely enough to avoid drift
- do not use a host-installed PostgreSQL instance for DocPilot when the project Docker Postgres is the documented source
