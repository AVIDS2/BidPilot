# 2026-07-18: Stripe billing control-plane hardening

## Why this change exists

The previous billing route treated a signed Checkout Session as the only stable
source of user/plan metadata and applied webhook mutations with no durable
receipt. That is not safe for a subscription product:

- Stripe does not automatically copy Checkout Session metadata onto the created
  Subscription; `subscription_data.metadata` is required.
- Stripe can retry a webhook and does not guarantee event delivery order.
- an existing Stripe customer must use the hosted Billing Portal rather than
  creating a second subscription Checkout session.

## Implemented behavior

- Checkout writes `user_id` and `plan` to both the Session and
  `subscription_data.metadata`, and uses `client_reference_id` as a second
  correlation identifier.
- `Subscription` stores Stripe customer/subscription IDs plus the latest
  applied Stripe event timestamp.
- `stripe_webhook_event` is a minimal receipt ledger keyed by Stripe event ID.
  It stores no raw payload or payment data. It retains only safe reconciliation
  identifiers (local user, Stripe customer/subscription), event timing, and
  outcome so support can explain a billing state without database poking.
- A webhook transaction inserts its receipt and updates local entitlement state
  atomically. A duplicate receipt returns success without applying a second
  mutation. A timestamp older than the last applied event is retained as an
  ignored receipt instead of rolling state backward.
- Subscription and invoice events resolve their local target through signed
  metadata first, then stored Stripe subscription/customer identifiers.
- `unpaid`, `canceled`, `incomplete`, `incomplete_expired`, and `paused` paid
  plan states no longer grant paid product entitlements. `past_due` remains a
  deliberate grace state until a later commercial policy introduces a bounded
  grace period.
- The account page opens the Stripe Customer Portal only for linked customers;
  unlinked users still go to pricing.
- Admin support can inspect safe per-user receipt outcomes through
  `GET /ops/billing/users/{user_id}/webhooks`; the endpoint never returns raw
  Stripe payloads.

## Required operator work before paid launch

1. Configure test/live Stripe price IDs, the destination signing secret, and
   Customer Portal capabilities in the Stripe Dashboard.
2. Register `https://bidpilot-api.rglens.com/billing/webhook` for Checkout,
   Subscription, and Invoice events documented in
   `docs/development/configuration-and-secrets.md`.
3. Retain test-mode proof for checkout, portal, cancellation, failed payment,
   successful renewal, duplicate delivery, and an out-of-order delivery.
4. Define organization/seat billing and receipt-retention policy before selling
   multi-user plans.

## Verification

- Focused billing, webhook, adapter, Ops, entitlement, readiness, and
  production-auth boundary coverage: `35 passed`.
- Full local release rehearsal after the receipt-support migration:
  Alembic upgrade, API Ruff, API `524 passed`, Worker Ruff, Worker `78 passed`,
  frontend TypeScript check, Vitest suite, and production Vite build.
- `uv lock --check` passed.

This is local regression evidence only. It does not prove a paid public launch:
the remaining operator evidence is a real Stripe test-mode rehearsal and a
controlled VPS pilot with retained artifacts.
