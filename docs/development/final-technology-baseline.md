# Final Technology Baseline

## Goal

Provide one compact summary of the accepted implementation baseline for `DocPilot`.

This document is intentionally redundant with ADRs and architecture docs so future implementation sessions can orient quickly without re-deriving the stack.

## Core rule

Use this baseline unless a later ADR explicitly changes it.

## Product shape

- product: `DocPilot`
- first scenario package: `BidPilot`
- category: enterprise AI document execution system

## Frontend baseline

- language: `TypeScript`
- framework: `React 19`
- build shell: `Vite`
- routing: `TanStack Router`
- server-state: `TanStack Query`
- styling: `Tailwind CSS v4`
- component foundation: `shadcn/ui`
- interaction primitives: `Radix` via shadcn-compatible primitives
- rich text: `TipTap`
- graph/workflow views: `React Flow`
- component documentation: `Storybook`
- flow verification: `Playwright`

## Backend baseline

- language: `Python 3.12+`
- API framework: `FastAPI`
- schema layer: `Pydantic v2`
- ORM: `SQLAlchemy 2`
- migrations: `Alembic`
- async jobs: `Celery`
- queue/cache broker: `Redis`

## Data baseline

- primary database: `PostgreSQL`
- vector storage: `pgvector`
- object storage: `MinIO` locally, `S3-compatible` contract for higher environments
- business truth location: `PostgreSQL`

## AI execution baseline

- execution runtime: `LangGraph`, behind an internal execution interface
- model providers: adapter-based, OpenAI-compatible plus domestic-provider support
- parser layer: adapter-based
- retrieval layer: adapter-based
- MCP: interoperability edge only, not internal control-plane truth

## Observability baseline

- telemetry: `OpenTelemetry`
- AI tracing and eval visibility: `Langfuse`
- health checks and smoke flows are required from Phase 0 onward

## Deployment baseline

- local stack: `Docker Compose`
- production posture: containerized deployment with hardening and promotion discipline
- future platform change: only by ADR when justified

## Workflow baseline

- control plane truth: `PostgreSQL`
- async dispatch: `Celery + Redis`
- intra-run AI workflow: `LangGraph`
- review and approval remain explicit product records, not hidden runtime state

## Default frontend quality bar

- workbench-style layout
- responsive by intent, not just shrink-to-fit
- evidence and review states visible
- Storybook-backed component states
- Playwright-backed user-flow verification

## Default backend quality bar

- thin route handlers
- service and repository separation
- durable run state
- append-only audit events
- adapters isolate providers and parsers

## Revisit triggers

Revisit this baseline only if:

- performance pressure justifies a new runtime split
- scale justifies service extraction
- product requirements justify a new first-class subsystem
- a new ADR supersedes the current choice
