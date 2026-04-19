# ADR 0002: Workflow and Execution Architecture

- Status: Accepted
- Date: 2026-04-18

## Context

`DocPilot` needs a workflow model that supports:

- long-running document processing
- durable execution state
- human review and rerun loops
- AI-specific orchestration without turning the entire product into an agent framework
- local development simplicity
- a clean path to production hardening

This project is not a generic workflow builder. It needs an internal execution architecture that is practical, inspectable, and evolvable.

## Decision

DocPilot will use a split execution model:

- `PostgreSQL` is the source of truth for workflow and run state
- `Celery + Redis` is the async task queue and worker dispatch layer
- `LangGraph` is the intra-run agent/workflow runtime behind an internal execution interface
- the API owns command intake and creation of durable run records
- workers own actual long-running execution and write outcomes back into relational state

## What each layer means

### PostgreSQL

Owns:

- execution run records
- task and status records
- review state
- deliverable state
- evidence and output versions
- audit events

PostgreSQL is never optional for workflow truth.

### Celery + Redis

Owns:

- job dispatch
- retries
- worker concurrency
- queue routing
- operational async delivery

Celery is the transport and task execution backbone, not the business state owner.

### LangGraph

Owns:

- AI-centric control flow within a run
- tool-calling loops
- stepwise drafting logic
- human-in-the-loop checkpoints inside an execution run

LangGraph is an execution engine detail, not the product control plane.

## Why this decision

### Why not LangGraph alone

LangGraph is good at durable, stateful agent execution, but DocPilot still needs explicit business truth and production-visible run state outside the agent runtime.

If LangGraph owns product truth directly, the system becomes harder to govern, inspect, and migrate.

### Why not Celery alone

Celery is strong for async task distribution and retries, but it is not the right abstraction for rich AI workflow logic, human-in-the-loop steps, or multi-step agent control flow by itself.

### Why not Temporal as the default

Temporal is powerful for crash-proof durable workflow execution, but it adds significant platform weight and operational complexity for a v1 product that still needs to prove scenario fit.

DocPilot should earn that complexity only if real execution pressure justifies it later.

### Why not Prefect as the default

Prefect is compelling for Python-native orchestration, especially data workflows, but DocPilot is not primarily a data pipeline platform. The product needs tighter control over business state, user-facing run semantics, and AI-specific execution composition.

## Alternatives considered

### Temporal

Rejected for v1 as the primary workflow engine because:

- it raises platform complexity too early
- it would shift too much architecture around one workflow engine decision
- the current product can get farther with Celery plus relational control-plane state

### Prefect

Rejected for v1 as the primary orchestration engine because:

- its strengths are more aligned with data pipeline orchestration
- DocPilot benefits more from a product-owned control plane and narrower AI execution runtime

### Build everything with a custom task runner

Rejected because it would recreate queueing, retries, and worker control badly.

## Consequences

### Positive

- clear separation between business truth and execution runtime
- local development stays practical
- AI workflow logic can evolve without rewriting control-plane storage
- queueing and retries are handled by mature async infrastructure

### Negative

- there are two workflow concepts to manage: durable product runs and intra-run execution graphs
- careful boundaries are required so status does not drift between Celery tasks and LangGraph nodes

## Follow-up rules

- all meaningful run state must be mirrored in relational records
- Redis must never be the sole source of critical workflow truth
- LangGraph state must be treated as execution state, not long-term product state
- any future move to Temporal or another workflow platform requires a new ADR and measured justification
