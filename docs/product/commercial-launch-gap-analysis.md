# DocPilot Commercial Launch Gap Analysis

## Purpose

This document records the current gap between DocPilot's present product state and a real public commercial launch.

It is intentionally stricter than the controlled pilot checklist. A controlled pilot can tolerate manual setup, named users, and known operational limitations. A commercial public launch cannot rely on those assumptions because unknown users can register, upload real business documents, trigger AI cost, request support, and expect payment/account/data flows to work reliably.

## Current judgement

DocPilot is past a pure MVP shell. It already has a real BidPilot scenario, durable domain models, authentication, organization and team concepts, email flows, provider configuration, assistant conversations, workflow execution, review, export, and production-readiness scripts.

The product is suitable for:

- founder-led demos;
- portfolio and interview storytelling;
- local or VPS rehearsals;
- controlled pilot use with named users and explicit limitations;
- a "real project that became a product" narrative around bid response and presales document execution.

The product is not yet ready for:

- open self-serve registration from unknown users;
- paid public launch;
- production use with sensitive third-party customer documents without operational guardrails;
- unlimited official-provider AI usage funded by the platform;
- a commercial SLA.

## Commercialization phases

### Phase A: Internal demo

Target:

- run locally or on a private VPS;
- demonstrate the product end to end;
- use seeded or non-sensitive documents;
- manually provision users and admin access.

Current state:

- mostly ready.

Remaining work:

- keep one reliable demo dataset;
- rehearse create project, upload, draft, review, export, and assistant flows;
- clean obvious UI inconsistencies before recording or presenting.

### Phase B: Controlled pilot

Target:

- onboard named users;
- limit usage manually or through simple backend limits;
- run on a hardened VPS deployment;
- collect feedback and validate output quality.

Current state:

- close, but not complete.

Remaining work:

- remove localhost links from production-facing email and billing flows;
- deploy API, web, worker, PostgreSQL, Redis, and object storage on the VPS;
- configure HTTPS, domains, CORS, SMTP, secrets, provider keys, and backups;
- verify one end-to-end workflow in the deployed environment;
- document known limitations before onboarding.

### Phase C: Public commercial launch

Target:

- unknown users can sign up, verify email, use trial credits, pay, upgrade, and safely upload documents;
- official-provider AI cost is bounded;
- support, backup, monitoring, and recovery are operational;
- subscription state and feature gates are enforced server-side.

Current state:

- not ready.

Remaining work:

- retain production usage evidence and enforce explicit hard cost ceilings;
- payment productionization;
- stronger rate limiting and abuse controls;
- production observability and alerting;
- customer-facing data retention and deletion policy;
- stronger tenant and project access verification;
- release process with rollback and restore drills.

## Product surface assessment

### BidPilot core workflow

Status:

- partially commercializable after pilot hardening.

What exists:

- project workspace;
- document bundle and source document model;
- parsed assets and knowledge chunks;
- requirement items;
- evidence records;
- deliverables and sections;
- section versions;
- execution runs;
- review comments and decisions;
- DOCX/PDF export paths.

Strength:

- This is the strongest part of the product. The domain is concrete and credible. Bid response, RFP handling, presales document drafting, evidence-backed generation, and review/export form a real business workflow.

Gaps:

- real-world large bundle reliability is not proven;
- output quality is not guarded by automated acceptance checks;
- evidence quality still needs real customer validation;
- reviewer workflow needs a non-developer acceptance pass;
- export fidelity needs real templates and stricter formatting expectations.

Launch implication:

- safe for demos and controlled pilots;
- not safe to promise "production bid response automation" until deployed E2E tests and real sample bundles pass consistently.

### AI workflow and assistant

Status:

- good foundation, not yet commercial-grade.

What exists:

- LangGraph-based worker workflow;
- server-side provider adapter strategy;
- server-side official-provider and BYOK configuration paths;
- assistant harness endpoint with structured SSE events;
- assistant confirmation cards and execution cards;
- assistant conversation history;
- generated conversation titles and manual rename;
- markdown and math rendering work in the assistant UI.
- typed provider failures, bounded transient retry, and redacted runtime events
  with user-facing recovery guidance;
- governed lifecycle capabilities for project creation, attachment ingestion,
  readiness, drafting, human review decisions, readiness-pack generation,
  approved export, and typed-confirmation deletion;
- durable Runtime events, replayable SSE progress, approval interrupts, and
  authenticated artifact downloads.

Strength:

- The architecture split is healthy: core document workflow remains LangGraph/workflow-oriented, while the assistant harness can behave like an operator that calls platform tools.

Gaps:

- organization security, membership, billing, provider credentials, and
  infrastructure controls intentionally remain human-only rather than being
  exposed as Agent tools;
- quality, cost, and error traces still need a production operations surface
  and measured user-facing explanations for partial/failing AI work;
- the four-report quality gate now includes AssistantBench routing/policy
  safety and can capture redacted Operator traces, but it still has only
  development fixtures rather than frozen regression/hidden release evidence;
- no approved cross-provider failover policy, vendor contract probe suite, or
  production provider-failure evidence.

Launch implication:

- assistant can be positioned as a governed pilot operator, not yet as a
  hands-off autonomous bid writer;
- workflow generation is quota-limited server-side, but commercial billing and
  full entitlement enforcement still need production completion.

### User, organization, and access control

Status:

- stronger than MVP, still needs production hardening.

What exists:

- user registration;
- email verification;
- login;
- password reset;
- refresh token storage and revocation;
- disabled users;
- admin role;
- organizations;
- teams;
- invitations;
- starter/professional/enterprise plan concept;
- admin-only audit and ops routes.

Strength:

- The system has enough identity structure to support a real pilot.

Gaps:

- production login, registration, password-reset, and email-resend limits plus the shared client-IP API budget now require Redis and fail closed on limiter outage; forwarded headers are trusted only from configured proxies, but IP reputation, WAF policy, account-takeover telemetry, and broader abuse detection still need public-launch controls;
- production auth depends heavily on `DOCPILOT_AUTH_REQUIRED=true`;
- tenant model is still effectively early-stage;
- project-level membership and access policy need a stricter audit before unknown customers use the system;
- no MFA, SSO, or enterprise identity provider;
- no mature account recovery/support workflow.

Launch implication:

- acceptable for controlled pilot;
- not enough for broad enterprise self-serve without more abuse and access-control hardening.

### Email system

Status:

- functional foundation, not production-polished.

What exists:

- SMTP adapter through `DOCPILOT_SMTP_*`;
- console fallback for development;
- verification email;
- password reset email;
- review notification email;
- account deletion confirmation email;
- invitation email.

Strength:

- Email flows are present and testable.

Gaps:

- deployment URL configuration exists, but every email link still needs a
  deployed-domain verification and delivery evidence;
- templates are basic and still branded like engineering emails;
- bounce handling, delivery monitoring, and sender reputation are not addressed;
- no async email job queue;
- no user-facing notification preferences.

Launch implication:

- configure SMTP for pilot;
- fix production URLs before VPS deployment;
- postpone advanced email deliverability until real usage grows.

### Billing and subscriptions

Status:

- code-level reconciliation is substantially hardened; live commercial launch
  remains unproven until a real Stripe test/live environment is rehearsed.

What exists:

- Stripe Checkout endpoint with deployment-configured return URLs;
- signed Stripe webhook handler with durable event-ID receipts and stale-event
  protection;
- subscription table;
- Stripe customer/subscription mappings and Customer Portal redirect for an
  existing billing customer;
- admin-safe webhook receipt lookup for customer-support reconciliation;
- starter/professional/enterprise plan states;
- durable official-provider usage ledger and server-side starter quotas for
  workflows, Assistant messages, and indexing.

Strength:

- The backend now keeps subscription truth on the server, makes duplicate or
  delayed webhooks safe, and prevents a second Checkout subscription for a
  customer who should use the hosted portal.

Gaps:

- no real Stripe test-mode or live-mode rehearsal has been retained as release
  evidence;
- Stripe Dashboard configuration (prices, webhook destination, Customer Portal
  capabilities) remains an operator task;
- invoices and receipts are visible through Stripe-hosted surfaces rather than
  an in-product invoice archive;
- refunds, disputes, tax, accounting exports, and payment settlement
  reconciliation are not implemented;
- organization subscription and Stripe seat-quantity foundations exist, but
  customer-facing seat remediation and the complete entitlement matrix are
  still unfinished;
- no complete pricing-to-feature entitlement matrix for seats, exports, BYOK,
  storage, and collaboration.

Launch implication:

- do not turn on paid public billing until the Stripe production configuration,
  controlled test-mode rehearsal, support runbook, and retained evidence are
  complete;
- free controlled pilot or manually upgraded plans remain the honest default
  until then.

### Provider keys and AI cost control

Status:

- security direction is correct, cost control incomplete.

What exists:

- server-side official provider key support;
- user BYOK provider configuration;
- encrypted provider key storage using `DOCPILOT_SECRETS_KEY`;
- masked key display;
- provider connection testing;
- Aliyun/DashScope env fallback for worker adapters;
- durable organization-scoped official usage records and starter quotas for
  workflow, Assistant, and indexing operations;
- provider-reported token ledger records for successful OpenAI-compatible,
  Anthropic, and LangChain operator calls, with official and BYOK separation;
- a mandatory staging/production platform-funded LLM token ceiling, combined
  with optional lower organization caps, conservative pre-dispatch
  reservations, settlement/release handling, and billing-owner-only change
  audit evidence;
- typed provider errors, bounded retry for transient failures, and redacted
  runtime/SSE recovery events.

Strength:

- The important security principle is already established: API keys do not belong in the frontend.

Gaps:

- the LLM token ceiling is now a default platform policy, but currency caps
  remain unavailable until a reviewed provider/model price catalog exists;
- server-owned embedding requests now share the same token ledger and platform
  ceiling as official LLM calls; currency reconciliation still needs a reviewed
  provider/model price catalogue and retained invoice evidence;
- no per-provider spend dashboard or provider invoice reconciliation;
- no retained production contract probes across every configured provider;
- no approved automatic cross-provider failover policy.

Launch implication:

- platform-owned official provider can be used for demo and limited pilot;
- public launch still requires a reviewed price policy, production telemetry,
  and real-provider release evidence before the platform funds unknown-user AI
  traffic.

### Deployment and operations

Status:

- documented path exists, real deployment still needs rehearsal.

What exists:

- deployment runbook;
- production readiness script;
- release checklist;
- backup and restore drill docs;
- environment matrix;
- health endpoints;
- structured logging foundation;
- Celery worker separation.

Strength:

- The project already thinks like a production system instead of only a local app.

Gaps:

- real VPS deployment is not yet verified end to end;
- domain, HTTPS, CORS, SMTP, secrets, object storage, and worker process management need to be exercised together;
- production readiness script does not prove every user-facing flow works;
- alerting and dashboards are not fully operational;
- restore drill must be run against the actual deployment shape.

Launch implication:

- one full VPS rehearsal is mandatory before any external pilot.

## Readiness scorecard

| Area | Current estimate | Public launch requirement |
|------|------------------|---------------------------|
| BidPilot workflow | 60-70% | stable E2E with real sample bundles |
| AI assistant | 50-60% | broader tool coverage, progress visibility, quota control |
| Authentication | 65-75% | durable rate limits, stricter access audit |
| Organizations and teams | 55-65% | clearer tenant/project permission model |
| Email | 55-65% | production URLs, SMTP verification, delivery monitoring |
| Billing | 60-70% code / 0% live evidence | Stripe rehearsal, organization seats, refunds/support operations |
| AI cost control | 65-75% | default token policy, reviewed price catalog, spend alerts, production telemetry |
| Deployment | 40-50% | VPS rehearsal, HTTPS, backups, monitoring |
| Observability | 35-45% | dashboards, alerts, trace correlation |
| Customer data governance | 40-50% | retention, deletion, export access, audit policy |

Overall:

- internal demo readiness: high;
- controlled pilot readiness: medium-high after focused hardening;
- public commercial readiness: medium-low until billing, quota, deployment, and ops are completed.

## Must-fix before VPS public pilot

These items block even a controlled external pilot unless explicitly waived.

1. Replace localhost URLs in email and billing flows with deployment-configured URLs.
2. Configure `DOCPILOT_AUTH_REQUIRED=true` and verify no protected route falls back to the dev user.
3. Configure production secrets: JWT secret, Fernet secrets key, SMTP, database, Redis, object storage, and provider key.
4. Deploy API, web, worker, PostgreSQL, Redis, and object storage together.
5. Put the API and web behind HTTPS domains.
6. Run migrations from an empty production-like database.
7. Create the first admin through the documented bootstrap flow.
8. Run one full project workflow on the VPS: create project, upload, parse, draft, review, export.
9. Confirm backup and restore procedure against the deployed database and storage.
10. Configure an explicit official-token cap for every pilot organization and
    verify its pre-dispatch rejection path.

## Must-fix before paid public launch

These items block commercial self-serve payment and broad public access.

1. Add paid entitlement checks for export, BYOK, storage, collaboration, and team seats.
2. Finish Stripe production configuration and retain a controlled test-mode
   checkout/portal/cancellation/failed-payment/retry rehearsal.
3. Add organization/seat billing before selling team plans.
4. Add production observability dashboards for API errors, queue depth, job duration, provider failures, export failures, AI cost, and billing outcomes.
5. Run release rehearsal and production readiness checks against the real deployment environment.
6. Add deletion/retention behavior that matches the written data policy,
   including a reviewed Stripe webhook receipt retention policy.
7. Run a security review of project/org access paths and provider key handling.
8. Introduce a reviewed provider/model price catalog, currency-cap policy, and
   spend/anomaly alerting before funding unknown-user AI traffic.

## Recommended first productionization spec

The first full implementation spec should focus on the smallest set that makes a controlled VPS pilot safe:

- production URL configuration cleanup;
- VPS deployment profile;
- auth-required production gate;
- SMTP production verification;
- official provider key configuration;
- durable workflow trial quota;
- one complete deployed E2E smoke test;
- backup and restore rehearsal;
- release checklist update.

The second productionization spec should focus on paid self-serve:

- Stripe production billing;
- subscription entitlement matrix;
- usage ledger;
- user billing page;
- payment failure and cancellation behavior;
- commercial observability dashboard.

## Interview and portfolio narrative

This project can be honestly framed as:

> DocPilot is an enterprise AI document execution platform. Its first scenario, BidPilot, targets bid response and presales proposal workflows. It ingests source document bundles, extracts requirements and evidence, generates reviewable draft sections with source attribution, routes output through human review, and exports final deliverables with audit history.

The strongest interview angle is not "I built an AI chatbot." The stronger angle is:

- business workflow ownership;
- durable state outside prompts;
- LangGraph as execution detail rather than product truth;
- provider adapters and BYOK security;
- human review and export governance;
- production readiness thinking around auth, billing, quotas, backups, and deployment.

The "contracted project that later became a product after the customer backed out" story is plausible because the scenario is concrete and the codebase reflects a real business workflow rather than a generic demo.

## Decision

The project should move next into a productionization planning phase, not another broad feature phase.

The immediate goal is:

- make the current BidPilot product safe to deploy to the VPS for controlled pilot use;
- avoid adding new scenario packages;
- avoid turning on paid self-serve until usage metering, billing, and operational controls are complete.

## Next document

After this analysis is approved, create:

`docs/superpowers/specs/YYYY-MM-DD-docpilot-vps-pilot-productionization-design.md`

That spec should define the concrete code and infrastructure changes required to reach a controlled VPS pilot.
