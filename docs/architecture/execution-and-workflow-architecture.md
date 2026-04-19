# Execution and Workflow Architecture

## Goal

Define how commands, runs, jobs, queues, and agent workflows fit together in `DocPilot`.

This document turns the workflow decision into an implementation structure.

## Core model

DocPilot has two layers of workflow:

### 1. Product workflow

This is the durable business workflow visible to users and operators.

Examples:

- bundle ingestion
- requirement extraction
- section drafting
- review and approval
- export generation

This layer must be represented in relational state and API-visible records.

### 2. Execution workflow

This is the internal run logic used to complete a product workflow step.

Examples:

- retrieve candidate evidence
- rank and filter context
- call model
- validate output
- branch for rerun or missing evidence

This layer may use `LangGraph`.

## Command lifecycle

The preferred execution sequence is:

1. API receives a command
2. API validates and persists command-related state
3. API creates an `ExecutionRun` or durable task record
4. API enqueues async work through Celery
5. worker claims the task
6. worker executes the relevant pipeline or LangGraph run
7. worker writes durable outcomes back to PostgreSQL
8. API and frontend read run state from PostgreSQL

## Workflow responsibilities by runtime

### API

Owns:

- synchronous validation
- command creation
- durable run initialization
- user-facing read models

### Worker

Owns:

- asynchronous execution
- parser and retrieval jobs
- draft generation
- validation and export jobs

### Celery

Owns:

- task routing
- queue naming
- retry handling
- worker delivery

### LangGraph

Owns:

- agentic step logic inside drafting or similar AI-heavy tasks
- step sequencing where loops, tools, and validation matter

## Initial workflow families

### Ingestion workflow

Stages:

- bundle registered
- source documents stored
- parse queued
- parse completed or failed
- normalized asset created
- chunks indexed

### Requirement extraction workflow

Stages:

- extraction queued
- candidate requirements produced
- structured requirement items persisted

### Drafting workflow

Stages:

- drafting queued
- evidence retrieved
- draft generated
- validation completed
- section version persisted

### Review workflow

Stages:

- review opened
- comment or rejection recorded
- rerun optionally requested
- approval recorded

### Export workflow

Stages:

- export requested
- approved sections gathered
- artifact rendered
- artifact stored
- export audit event written

## Status rules

### Run state

Use stable run states from the contract doc:

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`
- `partial_success`

### Section workflow state

Suggested initial section states:

- `not_started`
- `drafting`
- `draft_ready`
- `in_review`
- `changes_requested`
- `approved`
- `exported`

### Bundle workflow state

Suggested initial bundle states:

- `registered`
- `parsing`
- `parsed`
- `indexing`
- `ready`
- `failed`

## Queue strategy

Recommended initial queues:

- `ingest`
- `index`
- `draft`
- `review-side-effects`
- `export`

This should remain simple until real throughput requires more specialization.

## Scheduler policy

Initial policy:

- use API-triggered jobs and Celery task dispatch
- avoid adding a dedicated scheduler service until real recurring or delayed operational load requires it

Future extraction candidates:

- recurring maintenance jobs
- eval batch jobs
- cleanup and retention jobs

## Retry policy

- retries must be safe or explicitly guarded
- every retry should remain attributable in run history
- repeated failure should surface as durable failed state, not disappear into queue mechanics

## Human-in-the-loop policy

Human review is not modeled as a hidden LangGraph checkpoint alone.

Human actions must create durable business records:

- review thread state
- reviewer comments
- rejection reason
- approval decision
- rerun trigger

## Export policy

Exports must operate from approved and versioned content.

Do not export from transient draft buffers or non-durable in-memory state.

## Anti-patterns

- using Redis as workflow truth
- treating Celery task state as the only user-visible status
- storing critical review state only inside LangGraph memory
- combining API validation, worker orchestration, and provider logic in the same module

## Future revisit triggers

Revisit this architecture if:

- run recovery needs exceed Celery-based operational confidence
- delayed or recurring workflows become central
- cross-service execution coordination becomes too complex for the current split
- a dedicated workflow platform offers measurable benefits justified by production load
