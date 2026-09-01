# ADR 0001: Core Technology Stack

- Status: Accepted with frontend edge update (2026-09-01)
- Date: 2026-04-18

## Context

DocPilot needs to remain stable while AI tooling changes quickly. The stack must support:

- fast iteration
- strong typing at boundaries
- rich document-centric UI
- AI orchestration and parsing
- long-term maintainability
- clean deployment path from laptop to production

The system is expected to evolve for at least two years, so stable foundations matter more than chasing the newest full-stack trend.

## Decision

DocPilot will use the following primary stack:

- Frontend: `TypeScript + React 19 + Next.js 16 App Router`
- Backend API and worker runtime: `Python + FastAPI`
- Data store: `PostgreSQL + pgvector`
- Cache and queue broker: `Redis`
- Object storage: `MinIO` or `S3`
- Execution orchestration: `LangGraph` behind an internal engine interface
- UI layer: `Tailwind CSS + Kiranism dashboard source + shadcn/Base UI + TipTap + React Flow`
- Telemetry: `OpenTelemetry + Langfuse`
- VPS production deployment: `Docker Compose`; local app development uses direct Node/Python processes

## Why this decision

### React over Vue for this project

Vue remains strong for many domestic enterprise back-office systems, but React is a better fit for:

- AI-native streaming and workbench-style UI
- richer typed ecosystem alignment with modern AI SDKs
- stronger overlap with current AI product tooling

### Next.js as the presentation edge over FastAPI

The original Vite shell was replaced after the product UI review. Next owns the
browser-facing App Router and a thin BFF, while FastAPI remains the business
core. This gives:

- direct reuse of the reviewed Kiranism dashboard source
- route-level server rendering and loading behavior
- same-origin HttpOnly-cookie and SSE forwarding
- no migration of business state or Pi orchestration into Node

### Python over Java as the primary backend

Python is the best default for:

- parsing pipelines
- retrieval and ranking workflows
- agent orchestration
- AI provider integration
- evaluation loops

Java remains a future integration candidate, not the initial control-plane language.

### PostgreSQL over MySQL

DocPilot needs:

- relational integrity
- JSON metadata support
- event and audit queries
- vector retrieval in the same operational core

PostgreSQL fits this mixed workload better.

## Alternatives considered

### Vue + Nuxt

Rejected as the primary choice because the AI product ecosystem signal is weaker for this project shape, even though it remains a valid enterprise frontend stack.

### React + Next.js

Previously deferred because the first shell was a Python-backed Vite app. It is
now accepted for the presentation edge because the user-facing SaaS shell,
auth pages and responsive dashboard are the primary quality bottleneck. The
decision does not change the FastAPI/Pi control-plane boundary.

### Java + Spring as the main backend

Rejected for v1 because it slows delivery on AI-heavy workflows. Spring AI is increasingly relevant, but it is better used later for enterprise integration surfaces.

### Go or Rust as primary backend

Rejected because they introduce unnecessary multi-language complexity before real bottlenecks exist.

## Consequences

### Positive

- strong long-term stability in core layers
- direct fit for AI parsing and orchestration
- clear future path to Java, Go, or Rust only where justified

### Negative

- Python may require targeted optimization for heavy throughput paths later
- separate frontend/backend stacks require good API contracts

## Follow-up rules

- keep business truth in PostgreSQL
- keep AI framework dependencies behind adapters
- revisit language split only when measurable hot paths justify it
