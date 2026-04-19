# Security and Governance

## Objective

Make DocPilot safe enough to evolve into a real enterprise-facing system without retrofitting governance later.

## Core principles

- least privilege by default
- durable auditability
- explicit actor attribution
- secure secret handling
- no hidden side effects outside durable system records

## Identity and access

### Authentication

- Phase 0 and Phase 1 may use simplified development auth
- Phase 3 introduces production-ready authentication

### Authorization

Baseline roles:

- admin
- project editor
- reviewer
- read-only observer

Rules:

- write actions require authenticated actor context
- review decisions require reviewer or admin permissions
- export of approved deliverables must be policy-checked

## Audit rules

The system must record:

- who uploaded documents
- who triggered execution
- which provider or adapter version produced output
- who approved, rejected, or reran a section
- when exports were generated

Audit events must be append-only and queryable by project.

## Secrets handling

- no secrets committed to the repository
- local development uses `.env` or equivalent ignored files
- staging and production use a managed secret source where possible
- provider API keys are never exposed to the frontend

## Data handling

- raw documents live in object storage
- database stores metadata and durable workflow state
- sensitive documents should support scoped access by project
- generated output inherits project access rules

## Governance requirements

- all generation must be attributable to evidence or explicitly marked as missing evidence
- review decisions should remain in-system for traceability
- provider, parser, and prompt version metadata must be retained per execution run

## Security backlog for later phases

- RBAC policy enforcement middleware
- signed export access rules
- retention and archive policy
- tenant isolation model if the product becomes multi-tenant
