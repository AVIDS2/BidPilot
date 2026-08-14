# DocPilot Design Spec

## Goal

Build `DocPilot`, an enterprise AI document execution system that proves end-to-end capability across AI application, system, and platform layers. Its first scenario package, `BidPilot`, focuses on bid response, presales solution, and delivery document workflows.

## Product statement

DocPilot is not a chat wrapper and not a generic workflow builder. It is a project-based execution system for complex document work. It ingests document bundles, extracts structured requirements and evidence, creates execution plans, drafts deliverables, routes work through human review, records every AI and tool action, and produces auditable outputs.

## Why this project exists

The project is meant to demonstrate the following:

- business-facing AI application design
- durable system design for long-running, stateful workflows
- platform thinking around adapters, governance, observability, and deployment
- disciplined engineering choices in a fast-moving AI ecosystem

It fills the gap between the user's existing infrastructure-heavy projects and a product that shows practical end-user workflow ownership.

## Primary users

### Primary

- proposal managers
- presales engineers
- project delivery managers
- solution architects

### Secondary

- AI platform teams
- engineering managers evaluating enterprise AI system design
- reviewers interested in auditability, governance, and document traceability

## Product surfaces and audiences

DocPilot/BidPilot has three deliberately separate product surfaces. They may
share an identity provider and a common component library, but they must not
share navigation, default pages, or authorization scope.

### 1. Tenant administration console

Used by the customer organization's tenant administrators. It manages only
that organization's subscription/entitlements, workspace profile, members,
roles, response teams, approval rules, document templates, and approved AI or
integration capabilities. It must never expose other tenants or platform
operations.

### 2. Tenant bid workspace

Used by the people doing bid-response work: proposal managers, solution
architects, writers, commercial/legal contributors, and reviewers. Its primary
objects are opportunities, projects, source materials, requirements, response
plans, sections/evidence, review work, and deliverables. The AI Agent is a
first-class, tenant-scoped natural-language operator across this workspace; it
does not replace the human-operable work surfaces.

### 3. DocPilot internal operations console

Used only by DocPilot engineering, support, security, and operations staff. It
manages tenant lifecycle, product-level usage and billing, service health,
provider/MCP governance, incident response, release controls, and cross-tenant
audit under explicit internal authorization. It is deployed and authorized
separately from customer product surfaces.

Execution traces, provider diagnostics, and raw service logs are diagnostic
evidence. They are visible in context after a failed/recoverable business task
or to authorized operators; they are not a primary navigation destination for
ordinary bid users.

## Core problems to solve

1. large document bundles are hard to normalize into a consistent working set
2. requirements, evidence, and response content drift apart during execution
3. AI-generated outputs are difficult to verify, review, and trace back to sources
4. human review often happens outside the system, breaking version history and auditability
5. teams need project memory and reusable knowledge without losing scenario-specific context

## Scope

### In scope for DocPilot

- project workspace creation
- document bundle ingestion
- parsing pipeline orchestration
- retrieval and evidence generation
- execution planning and task graph creation
- section drafting and structured generation
- human review, approval, rejection, rerun, and version diff
- audit logs, model/tool traces, and cost tracking
- export of final deliverables

### In scope for BidPilot v1

- bid response projects
- presales solution pack assembly
- enterprise delivery document generation
- requirement matrix extraction
- section-level evidence-backed drafting
- reviewer comments and approval flow

### Explicit non-goals

- generic no-code workflow builder
- autonomous outbound communications platform
- ERP replacement
- full document office suite
- multi-industry verticalization in v1
- custom model training platform as a core product surface

## Product architecture

DocPilot consists of four logical planes.

### 1. Control plane

Owns the project workspace and all durable business state:

- projects
- bundles
- source documents
- tasks
- deliverables
- review states
- evidence records
- audit events

This plane is the source of truth and must remain independent from any one agent runtime.

### 2. Execution plane

Runs long-lived tasks such as:

- parse and normalize
- chunk and index
- retrieve and rank
- draft
- validate
- rerun with new evidence

This plane may use LangGraph internally but must expose execution through stable platform services and persist all meaningful outcomes back into the control plane.

### 3. Integration plane

Provides adapters for:

- model providers
- embeddings and rerankers
- parsers and OCR engines
- storage providers
- MCP tools and external APIs
- export targets

All adapters are replaceable.

### 4. Operations plane

Provides:

- authentication and RBAC
- audit logs
- traces and metrics
- evaluation data
- release and incident procedures

## Initial technology direction

- Frontend: `TypeScript`, `React`, `Vite`
- UI: `Tailwind CSS`, `shadcn/ui`, `TipTap`, `React Flow`
- Backend API: `Python`, `FastAPI`, `Pydantic v2`, `SQLAlchemy 2`
- Background jobs: `Celery`, `Redis`
- Database: `PostgreSQL`, `pgvector`
- Object storage: `MinIO` or `S3`
- Execution orchestration: `LangGraph` behind an internal execution interface
- Observability: `OpenTelemetry`, `Langfuse`
- Deployment: `Docker Compose` first, `Kubernetes-ready` architecture

### Managed infrastructure policy

The product may use Supabase as a managed implementation of PostgreSQL,
pgvector, object storage, authentication, realtime collaboration, backups, and
infrastructure administration. These are reusable infrastructure concerns and
must not be reimplemented by BidPilot.

FastAPI remains the business control-plane boundary. Browser clients call
BidPilot APIs rather than directly holding administrative database or storage
credentials. BidPilot owns its domain model, tenant authorization, approval
policy, document parsing/OCR orchestration, evidence extraction, LangGraph
workflows, Agent capability governance, and product audit semantics.

Raw source files belong in managed object storage; PostgreSQL stores metadata,
references, lifecycle state, and structured business truth. Supabase secret or
service-role credentials are server-only and must never reach browser bundles.

## Architecture constraints

- business truth must remain in `PostgreSQL`
- AI components must be pluggable through adapters
- the system must run locally in development without cloud-only dependencies
- deployment must support both single-node and future multi-service modes
- every generation action must be traceable to evidence, inputs, and actor
- every customer-facing screen must expose a meaningful human action or an
  actionable decision; passive runtime logs do not qualify as a product work
  surface
- tenant data, tenant administration, and internal platform operations must
  remain separately authorized and separately navigated

## Key domain concepts

- `Project`: top-level execution container
- `Bundle`: logical collection of uploaded source materials
- `SourceDocument`: original artifact with metadata and storage path
- `ParsedAsset`: normalized parse result
- `KnowledgeChunk`: indexed retrieval unit
- `Evidence`: source-backed citation record used by outputs
- `ExecutionRun`: one run of an execution graph
- `Task`: durable execution or review unit
- `Deliverable`: output artifact such as bid response, solution section, or delivery pack
- `ReviewThread`: human review discussion and decision chain
- `AuditEvent`: immutable event record for governance

## Quality attributes

### Must optimize for

- iteration durability
- auditability
- composability
- local development reliability
- deployment simplicity in early phases
- smooth path to production hardening

### Must avoid

- AI framework lock-in
- generic platform sprawl before scenario fit
- excessive microservice split in early phases
- hiding business state inside prompts or runtime memory only

## Phase model

### Phase 0: foundation

- repo bootstrap
- environment model
- data model skeleton
- local deployment stack
- observability skeleton

### Phase 1: BidPilot core

- project workspace
- ingestion and parsing flow
- retrieval and evidence
- requirement matrix
- section drafting

### Phase 2: review and governance

- review workflow
- version diff
- approval gates
- audit and trace views
- export pipeline

### Phase 3: production hardening

- auth and RBAC
- failure handling
- backup and restore
- deployment automation
- cost and quality dashboards

### Phase 4: scenario expansion

- reusable scenario packages
- richer connectors
- more advanced execution templates

## Success criteria

The project is successful when it can demonstrate all of the following in one coherent product:

- upload a realistic project bundle
- extract structured requirements and evidence
- generate section drafts with source attribution
- support reviewer comments, rejection, rerun, and approval
- export a reviewable deliverable
- show complete audit history and traceability
- run locally and deploy through a repeatable process

## Risks and mitigations

### Risk: framework churn

Mitigation:

- keep execution framework behind an internal engine interface
- keep project truth in relational storage

### Risk: platform overreach

Mitigation:

- keep `BidPilot` as the first scenario package
- reject generic builder features until the scenario is complete

### Risk: implementation sprawl

Mitigation:

- phase plans remain sequential and independently demonstrable
- no feature enters scope without a visible scenario owner

## Document status

- Status: approved for planning
- Intended use: project charter, design source of truth, planning input
