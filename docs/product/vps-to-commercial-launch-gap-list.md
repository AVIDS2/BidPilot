# VPS Pilot to Commercial Launch Gap List

This document captures what is still missing after the current VPS pilot hardening work.

## Already covered

- server-side auth enforcement;
- email verification and SMTP delivery;
- project/org access isolation;
- starter workflow usage quota enforcement;
- user-configurable provider keys with encrypted storage;
- production readiness checks for environment variables;
- basic payment scaffolding and admin plan updates;
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
- invoice and receipt handling;
- subscription cancellation/reactivation flows surfaced in UI;
- webhook monitoring and replay procedure.

### Identity and access

- org invitation and role-management flows for non-admin operators;
- password reset and login support validation across real mail delivery;
- lockout/abuse controls backed by durable storage;
- audit review for high-risk actions.

### AI and usage control

- durable monthly usage ledger and plan-based reset window;
- per-feature gating beyond project count;
- assistant and workflow quotas exposed in UI;
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
