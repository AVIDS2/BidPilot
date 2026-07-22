# Stripe Test Mode Rehearsal

## Purpose

This runbook produces the commercial evidence required before BidPilot enables
paid self-service. It is for Test Mode only. It does not authorize a live Stripe
launch, and no screen recording, terminal artifact, or repository file may
contain API keys, webhook secrets, card data, customer email addresses, or raw
webhook payloads.

## Preconditions

1. Deploy the reviewed commit and apply all migrations, including
   `f6a7b8c9d0e1_add_stripe_receipt_organization_mapping`.
2. Create a Stripe Test Mode recurring price for each enabled plan. Each price
   must use Stripe's `licensed` usage type so its Subscription item quantity is
   the purchased seat count.
3. Configure the deployment environment with the Test Mode secret key,
   destination-specific webhook signing secret, and Professional price ID. The
   Enterprise price ID is optional until that plan is offered.
4. Register the API webhook destination at
   `https://bidpilot-api.rglens.com/billing/webhook` and subscribe to:
   `checkout.session.completed`, `customer.subscription.created`,
   `customer.subscription.updated`, `customer.subscription.deleted`,
   `invoice.paid`, and `invoice.payment_failed`.
5. In the Customer Portal, allow payment-method updates, configured plan
   switching, and cancellation. Keep **quantity changes** disabled until the
   explicit seat-overage/remediation workflow is implemented and rehearsed.
   BidPilot reconciles plan switching from the actual Subscription item Price
   ID rather than Checkout metadata.

## Read-only preflight

Run inside the API container or deployment environment after injecting Test Mode
configuration:

```powershell
python scripts/stripe_test_mode_preflight.py
```

The command performs only Stripe Price retrieval. A passing result says the
configured prices are active and `licensed`; it does not create customers,
Checkout Sessions, subscriptions, or webhook destinations.

## Manual evidence sequence

1. Create a fresh test workspace with one owner and begin a Professional
   Checkout. Verify the redirect was initiated by the owner and the line item
   shows one licensed seat.
2. Complete Checkout using Stripe's published Test Mode card flow. Retain the
   redacted Checkout Session and local workspace identifiers in the restricted
   evidence set.
3. Verify the signed `checkout.session.completed` and
   `customer.subscription.created`/`updated` events create one organization
   receipt, preserve the local billing owner, set the paid plan, and set the
   organization seat limit from the Subscription item quantity.
4. Invite and accept one additional member only after raising the Test Mode
   quantity through an approved operator rehearsal. Confirm that both members
   share the workspace quota and that an excess invitation remains pending.
5. Open the Customer Portal as the workspace owner. Confirm a non-owner is
   denied by the API before a portal session is created.
6. Re-deliver one prior webhook event and confirm it is recorded as a duplicate
   without changing the organization entitlement. Deliver an older state after a
   newer one and confirm it is ignored as stale.
7. Rehearse cancellation, failed invoice, and a later successful invoice. Each
   state must update the organization record through a signed event and appear
   in the safe receipt ledger.

## Pass criteria

- The preflight passes with Test Mode credentials and active licensed prices.
- Checkout, Portal, and webhook events all resolve to the same local
  organization and billing owner.
- A duplicate or stale event cannot change entitlement state twice or backwards.
- No event can create a new organization subscription from metadata alone.
- No evidence artifact contains secrets, personal source documents, or raw
  Stripe webhook data.

## References

- [Stripe metadata propagation](https://docs.stripe.com/metadata/use-cases)
- [Stripe per-seat quantities](https://docs.stripe.com/billing/subscriptions/quantities)
- [Stripe Customer Portal configuration](https://docs.stripe.com/customer-management/configure-portal)
