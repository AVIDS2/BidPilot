# Guided First-Run Demo Workspace Design

## Status

- Date: 2026-07-19
- Status: Approved implementation slice
- Depends on: `2026-07-14-bidpilot-product-agent-refoundation-v2-design.md`

## Problem

A newly registered user currently reaches an empty workspace and a passive
three-step explainer. That does not demonstrate BidPilot's differentiated
workflow, nor does it help a non-developer understand why the product exists.

The product strategy requires a guided first run and a sample dataset. The
commercial launch gap list also identifies external-pilot onboarding as open.

## Decision

Add a user-owned, built-in **Demo Workspace** that creates a small, explicitly
labeled BidPilot project from deterministic sample sources.

The demo workspace is not a simulated model run. It contains transparent
sample documents, a small Requirement Ledger, source-linked evidence, default
deliverable sections, and an audit event that identifies the seed operation.
It deliberately does not create generated drafts, invoke a model, enqueue a
worker, consume an AI quota, or claim production-quality extraction.

## User Flow

1. A user with no projects sees a choice between creating a workspace from
   their own tender files and exploring the guided demo workspace.
2. Choosing the demo creates (or reopens) the user's existing demo workspace.
3. The project opens on the real project workbench, where the user can inspect
   source documents, requirements, evidence, readiness gaps, audit records,
   and the default response structure.
4. Starting a real parse, retrieval, draft, review, or export remains an
   ordinary governed platform action with its own approval, quota, and
   provider requirements.

## Data and Security Contract

- The endpoint requires an authenticated user and creates the project only in
  that user's active organization.
- It obeys the normal project-count entitlement. A returned existing demo does
  not consume another project slot.
- At most one active demo workspace is reused per user and organization. A
  deleted demo may be created again.
- Built-in documents are served through the same authenticated document
  download endpoint; they do not require object storage and never become
  shared customer content.
- Demo records use an explicit built-in storage prefix and an audit event;
  they are never mistaken for user uploads or AI-generated output.
- The server writes no provider credential, prompt, model output, or external
  request while creating a demo workspace.

## Scope

### In scope

- A `POST /projects/demo` command returning an existing or newly seeded
  project.
- Deterministic documents, requirements, evidence, and source locators.
- Project quota, membership, audit, and normal deletion semantics.
- Empty-workspace and onboarding entry points in the web application.
- API and frontend tests covering idempotency and public data boundaries.

### Out of scope

- Auto-running extraction, embedding, drafting, review, or export.
- An artificial completed workflow graph or generated SectionVersion.
- Replacing the separate user-file onboarding path.
- A shared organization demo project visible to other users.

## Acceptance Criteria

- A first-time user can create a demo workspace without configuring a model or
  object-storage upload.
- The project contains three downloadable built-in markdown sources, a
  Requirement Ledger with source locators, linked evidence, default sections,
  and a `project.demo_seeded` audit event.
- Repeating the request returns the same active demo workspace for the same
  user and organization and does not create a second project.
- A demo workspace consumes one normal project entitlement when first created.
- The demo path does not invoke Celery, a provider adapter, or a usage ledger.
- All records remain inaccessible to users without project membership.
