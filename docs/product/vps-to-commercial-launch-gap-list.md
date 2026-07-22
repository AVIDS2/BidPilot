# VPS Pilot to Commercial Launch Gap List

This document captures what is still missing after the current VPS pilot hardening work.

## Already covered

- server-side auth enforcement;
- email verification and SMTP delivery;
- project/org access isolation;
- starter workflow usage quota enforcement;
- durable Assistant/workflow/indexing usage ledger and starter budgets;
- user-configurable provider keys with encrypted storage;
- production readiness checks for environment variables;
- Stripe Checkout/Customer Portal routing, signed webhook reconciliation, and
  user-level entitlement updates;
- release rehearsal and backup/restore runbooks.

## Still missing before public commercial launch

### Product

- customer onboarding flow for external pilot users;
- polished plan/upgrade/purchase copy;
- clearer assistant error handling for all non-403 failures;
- end-to-end product analytics and event review;
- customer support entry points and SLA wording.

### Billing

- live Stripe or equivalent payment settlement in a real launch environment;
- retained Stripe test-mode and live-mode rehearsal evidence;
- Stripe Dashboard price, webhook, and Customer Portal configuration operated
  on the real deployment;
- in-product invoice/receipt history, refunds, disputes, and settlement
  reconciliation;
- organization/seat billing and shared-entitlement rules;
- webhook outcome monitoring, alerts, and a reviewed receipt-retention policy.

### Identity and access

- org invitation and role-management flows for non-admin operators;
- password reset and login support validation across real mail delivery;
- lockout/abuse controls backed by durable storage;
- audit review for high-risk actions.

### AI and usage control

- per-feature gating beyond projects, workflow, Assistant, and indexing;
- organization-level AI budgets and provider-spend ceilings;
- provider health monitoring and fallback routing;
- operator visibility into provider spend.

### Operations

- production secrets management outside plain `.env`;
- backup restore drill on the actual VPS target;
- log retention and alert routing;
- smoke checks wired into deployment promotion;
- rollback ownership and release owner process.

### Supportability

- customer-facing documentation for setup and troubleshooting;
- admin runbook for user support and subscription corrections;
- incident template and escalation path;
- named owner for billing/support decisions.

## Launch bar

Commercial launch should wait until:

- at least one non-developer can onboard, pay, and complete a core workflow;
- billing and quota behavior are visible and supportable;
- backups, restore, and rollback are rehearsed on the real deployment target;
- support ownership is assigned and documented.
