# DocPilot Paid Public Launch Design

## Status

- Status: draft for owner review
- Date: 2026-06-15
- Source analysis: `docs/product/commercial-launch-gap-analysis.md`
- Scope: paid public launch after controlled VPS pilot

## Goal

Make DocPilot ready for a real paid public launch where unknown users can sign up, verify email, buy a plan, see their entitlements, and use the product without the platform losing control of AI cost, subscription state, or supportability.

The target outcome is a commercial workflow where a customer can self-serve onboarding, payment, subscription management, quota tracking, and cancellation, while the operator can reconcile billing state, usage state, and customer support actions from the backend.

## Non-goals

This spec does not ship every enterprise capability.

Out of scope for this phase:

- enterprise SSO or MFA;
- Kubernetes or multi-region infrastructure;
- a full customer support desk;
- public SLA or legal/compliance policy work;
- a custom billing replacement for Stripe;
- advanced analytics warehouse work;
- a visual workflow builder;
- new scenario packages beyond BidPilot.

## Operating assumptions

- The controlled VPS pilot from the previous phase is already in place and stable.
- `bidpilot.rglens.com` is the product web origin and `api.bidpilot.rglens.com` is the API origin.
- Official provider keys remain server-side only.
- BYOK provider keys remain encrypted at rest.
- Public users may be unknown, so every entitlement decision must be enforced on the backend.
- Stripe is the initial payment processor unless the owner explicitly chooses another provider later.

## Release target

The public launch should support:

- public sign-up and email verification;
- paid plan purchase and upgrade through Stripe;
- subscription state visible in the UI;
- durable monthly usage ledger;
- trial, paid, and BYOK entitlements enforced server-side;
- cancellation and reactivation paths;
- invoice/receipt visibility through Stripe-hosted surfaces or stored metadata;
- billing and support admin reconciliation;
- customer-facing quota and plan messaging;
- operator-visible spend and usage reporting.

## Architecture

### Commercial control plane

The commercial launch should treat billing and usage as first-class backend state, not as UI decoration.

The backend owns:

- plan state;
- subscription state;
- usage accounting;
- trial reset windows;
- quota enforcement;
- entitlement checks;
- provider source classification;
- audit events for billing decisions.

The frontend only presents the current state and calls backend endpoints. It must never decide whether a request can spend money or consume a paid entitlement.

### Stripe-centered payment flow

Stripe is the initial public payment mechanism because the codebase already has a checkout and webhook scaffold.

The launch should support:

- checkout creation for professional and enterprise plans;
- webhook reconciliation for successful payment and cancellation;
- customer-facing plan and billing pages;
- a cancellation path that keeps access consistent until the billing period ends if Stripe reports that behavior;
- stored metadata that links subscription events back to a user and organization.

This phase should not invent a custom payment ledger if Stripe can provide the source of truth for invoices and receipts.

### Usage and entitlement model

Commercial launch requires a durable usage ledger because plan state alone cannot bound AI cost.

The backend should record:

- official-provider workflow runs;
- assistant usage if it can incur provider cost;
- export or other cost-bearing jobs if they become metered later;
- quota denials and plan upgrades as auditable product events.

Entitlements should be computed from:

- plan;
- usage window;
- provider source;
- ownership/org membership;
- admin overrides.

### Support and operator model

The operator must be able to answer four questions without reading logs manually:

1. What plan is this customer on?
2. How much usage have they consumed this month?
3. Why was a request blocked?
4. What billing event last changed their state?

That means the backend needs dedicated admin/support views or endpoints for subscription and usage reconciliation.

## Required code changes

### Payment and subscription state

Problem:

- Billing exists, but the product cannot yet be safely sold to unknown users.

Design:

- Keep Stripe as the payment processor.
- Add explicit subscription state transitions in the backend for active, past_due, canceled, and unpaid-like states.
- Make checkout success, cancel, and return URLs derive from the configured app URL.
- Store enough metadata to reconcile webhook events with a user and organization.
- Add a customer-facing billing page that reflects current state rather than implying everything is static.

Acceptance:

- Checkout creates a Stripe session for the correct plan.
- Webhook handling updates the local subscription state deterministically.
- The UI shows whether the plan is trial, starter, professional, enterprise, canceled, or blocked by billing.
- The system does not rely on the frontend to decide subscription truth.

### Durable usage ledger

Problem:

- The current workflow quota is only the first step; public launch needs monthly accounting and supportability.

Design:

- Add a durable usage ledger table.
- Record at least:
  - user;
  - org;
  - project;
  - event type;
  - provider source;
  - units;
  - window key or billing period key;
  - created time;
  - metadata.
- Use the ledger to compute monthly quota, paid entitlement usage, and support lookups.
- Keep official-provider and BYOK usage separate.

Acceptance:

- The backend can answer current-period usage for a user and organization.
- The backend can block a request when monthly quota is exhausted.
- The backend can explain the block reason through a stable error shape.
- Usage events are queryable by operator/admin flow.

### Plan and entitlement matrix

Problem:

- Project count limits exist, but paid launch needs a real entitlement matrix.

Design:

- Define plan-to-feature entitlements in one backend source.
- At minimum, gate:
  - project count;
  - workflow run quota;
  - assistant usage policy;
  - BYOK enablement;
  - team seat count if applicable;
  - export caps if the product needs them later.
- Keep the matrix simple and explicit rather than clever.

Acceptance:

- Starter users are blocked from paid-capacity features after their trial window or quota window ends.
- Professional and enterprise users have the intended expanded access.
- Admin overrides remain possible for support.

### Public onboarding flow

Problem:

- Unknown users need a stable path from landing page to account to payment.

Design:

- Keep the current sign-up and email verification flow.
- Add clear plan selection in onboarding and pricing.
- Make the upgrade path obvious without forcing a sales conversation.
- Preserve the manual/invite path for private accounts.

Acceptance:

- A new user can sign up, verify email, view plans, and reach checkout.
- A signed-in user can understand their current plan and next upgrade step.
- The invite path still works for non-self-serve customers.

### Billing/support admin tools

Problem:

- Public billing needs an operator to fix issues without database poking.

Design:

- Add support-facing admin views or endpoints for:
  - subscription lookup;
  - usage lookup;
  - entitlement explanation;
  - manual plan correction;
  - webhook reconciliation status.
- Keep this behind admin auth.

Acceptance:

- An admin can inspect a user's current billing state and usage.
- An admin can correct a broken subscription state without editing raw tables.
- Support actions are audited.

### Billing observability

Problem:

- Commercial launch needs to know when money-related flows fail.

Design:

- Add structured logging and audit events for checkout creation, webhook receipt, subscription change, quota denial, and plan upgrade.
- Add a minimal release smoke that confirms billing surfaces and plan state are reachable.
- Keep a future path open for dashboards, but do not require a full BI stack in this phase.

Acceptance:

- Billing failures are visible in logs and audit trails.
- The operator can detect webhook failures and quota denials.
- Release smoke includes billing-critical endpoints.

## Required documentation changes

Update:

- `docs/ops/release-checklist.md`;
- `docs/ops/deployment-and-runbook.md`;
- `docs/product/known-limitations.md`;
- `docs/product/vps-to-commercial-launch-gap-list.md`;
- `docs/development/configuration-and-secrets.md` if billing secrets or webhook config need clarification.

Documentation must clearly distinguish:

- controlled VPS pilot;
- paid public launch;
- future enterprise hardening.

## Security requirements

- No payment secrets in frontend code or frontend env files.
- Stripe secrets and webhook secrets stay server-side only.
- Subscription truth must come from backend reconciliation, not client storage.
- Billing support endpoints must be admin-gated.
- Quota decisions must happen before provider calls.
- Audit logs must not include card data or secret payloads.

## Testing strategy

Backend tests:

- checkout success/cancel URL generation;
- webhook reconciliation;
- monthly usage ledger aggregation;
- quota/entitlement blocking;
- admin support lookup;
- manual plan correction;
- BYOK bypass where appropriate.

Frontend tests:

- pricing copy and onboarding flow;
- billing page state rendering;
- plan status badges;
- quota and billing error display.

Smoke tests:

- sign up and verify email;
- open pricing page;
- enter checkout path;
- confirm subscription state visible after webhook simulation;
- verify a blocked action surfaces a stable product error.

## Acceptance criteria

The paid public launch phase is complete when all of the following are true:

1. A new user can sign up and verify email on the public site.
2. A user can buy a supported plan through Stripe checkout.
3. Webhook events update local subscription state reliably.
4. The UI shows current plan and billing state.
5. Monthly usage is recorded durably and blocks are enforced server-side.
6. Quota, entitlement, and provider-source rules are explainable in the backend.
7. Admin support tools can inspect and correct subscription state.
8. Billing-related failures are visible in logs or audit trails.
9. Release checklist and docs describe the launch path clearly.
10. No payment secret or provider key is exposed to the frontend.

## Rollout plan

### Milestone 1: Billing state and usage model

- define subscription state;
- define usage ledger shape;
- define entitlement matrix;
- add supporting tests.

### Milestone 2: Stripe reconciliation and billing UI

- solidify checkout and webhook flow;
- add billing page state;
- add support/admin lookup surfaces;
- add tests.

### Milestone 3: Launch readiness

- update docs and release checklist;
- add smoke checks;
- verify quota and billing failure paths;
- rehearse plan correction and webhook replay.

## Risks

### Risk: billing logic leaks into the frontend

Mitigation:

- keep truth in backend tables and service methods;
- frontend only mirrors state.

### Risk: webhook events arrive out of order or twice

Mitigation:

- make reconciliation idempotent;
- store event metadata and processed state;
- prefer backend state machine updates over one-off inserts.

### Risk: usage accounting becomes too clever

Mitigation:

- start with one durable ledger;
- keep event types explicit;
- avoid generalized metering until needed.

### Risk: public launch claims outrun ops maturity

Mitigation:

- keep the product conservative about plan promises;
- require release rehearsal and billing smoke before launch.

## Deferred to future enterprise hardening

- SSO/MFA;
- advanced invoice automation;
- refund automation;
- deep analytics warehouse;
- enterprise seat management;
- public SLA and support contract;
- multi-region billing recovery.

## Next step

After owner review, create the implementation plan:

`docs/superpowers/plans/2026-06-15-docpilot-paid-public-launch.md`

That plan should break this spec into small, testable tasks with exact files, tests, commands, and checkpoints.
