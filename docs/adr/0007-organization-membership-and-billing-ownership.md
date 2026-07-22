# ADR 0007: Organization Membership and Billing Ownership

- Status: Accepted
- Date: 2026-07-18

## Context

BidPilot is a project-based team product. Projects, bundles, workflow runs, and
usage events already carry an organization identifier, but the current identity
and billing model is still effectively user-owned:

- `User.org_id` is both a user's only organization relationship and active
  organization pointer.
- switching organizations mutates that value without a durable membership
  record.
- `Subscription` is one-to-one with `User`.
- official-provider quotas are counted by user even though the usage records
  also know the organization.

That model is acceptable for a named-user pilot, but it cannot safely sell a
team plan. It cannot answer who owns a workspace, who consumes a seat, which
organization pays for a shared project, or whether a user who belongs to two
organizations is authorized to switch context.

Stripe's documented per-seat model represents each licensed user as a
subscription quantity. Stripe also documents that webhook delivery can be
duplicated and out of order. The local product must therefore own membership,
authorization, and entitlement truth; Stripe is the external payment and
reconciliation system, not the source of application authorization.

References:

- https://docs.stripe.com/subscriptions/pricing-models/per-seat-pricing
- https://docs.stripe.com/billing/subscriptions/quantities
- https://docs.stripe.com/webhooks

## Decision

### 1. Organization is the commercial workspace boundary

Paid plan, seat capacity, official-provider quota, storage quota, collaboration
entitlements, and billing identifiers belong to an organization. A user may
belong to multiple organizations and only receives the entitlements of the
active organization for a request.

Project membership remains a narrower authorization boundary inside an
organization. Team membership remains a grouping mechanism and does not imply a
paid seat or project access by itself.

### 2. Add explicit organization memberships before changing billing

Introduce an `OrganizationMembership` record with:

- `org_id`, `user_id`, and a single reusable row per pair;
- `role`: `owner`, `admin`, or `member`;
- `status`: `active` or `removed`;
- lifecycle timestamps and an auditable actor.

The existing `User.org_id` remains temporarily as the active-organization
pointer for compatibility. Every authorization path that uses it must first
verify an active membership. A later cleanup may rename it to
`active_org_id`; that rename is deliberately not part of the first migration.

The migration backfills one active membership for each existing `User.org_id`.
For an existing organization with several users, the earliest existing user is
assigned `owner` and the remaining users are assigned `member`; migration output
must make this deterministic and visible for operator review. An organization
must always retain at least one active owner.

### 3. Add an organization subscription; retain user subscriptions only as migration fallback

Introduce `OrganizationSubscription`, keyed one-to-one by `org_id`, with:

- plan and lifecycle status;
- `seat_limit` and billable seat count snapshot;
- Stripe customer, subscription, and subscription-item identifiers;
- last-applied Stripe event timestamp;
- `billing_owner_user_id` constrained to an active owner; and
- creation/update timestamps.

The current user-level `Subscription` is not deleted in the first release.
The entitlement resolver chooses an active organization subscription first and
only falls back to the user's legacy subscription when the organization has no
subscription. This avoids a destructive data migration and prevents an inactive
or canceled legacy subscription from granting a paid organization entitlement.

### 4. Centralize entitlement resolution

All plan checks must receive an organization scope and resolve a single
`EntitlementContext` containing the effective plan, status, seat capacity, and
feature limits. This replaces direct user-subscription lookups in project
creation, official-provider workflow, Assistant, indexing, export, BYOK, and
collaboration checks.

Usage events continue to retain both actor and organization for audit. Official
quota aggregation moves to organization scope so two members of one paid
workspace share the purchased allowance, while two organizations of the same
user do not.

### 5. Seat changes are governed local actions, not a browser-side Stripe field

An active organization membership consumes one seat. Invitations do not consume
a seat until acceptance. Creation or reactivation must be denied when it would
exceed `seat_limit`.

The first paid release does not silently change a Stripe subscription when a
member is invited. Instead, a billing owner purchases or adjusts capacity using
an explicitly configured Stripe Checkout or Customer Portal flow, and signed
webhooks reconcile the resulting Stripe quantity into `seat_limit`. This avoids
local/Stripe divergence from an untracked seat mutation. A later self-service
seat-adjustment flow must use a durable pending action plus Stripe idempotency
keys and reconciliation events.

### 6. Billing authority is narrow and explicit

Only an active organization `owner` can start Checkout, open the Billing Portal,
or change seat capacity in the first release. `admin` can manage members and
projects but cannot create a financial commitment. Global platform administrators
remain a separate operational role and do not implicitly become customer billing
owners.

### 7. Webhook reconciliation stays idempotent and organization-scoped

Stripe Checkout and subscription metadata must carry `org_id`, plan, and the
billing-owner identifier. A signed webhook receipt is stored exactly once;
out-of-order events are rejected by the subscription state timestamp. Unknown or
membership-invalid metadata is recorded as safely ignored and never creates an
organization entitlement.

## Consequences

### Positive

- collaboration, seats, and paid quota use the same commercial boundary;
- switching organization context becomes authorization-safe;
- user activity stays attributable without leaking a paid plan across tenants;
- Stripe remains replaceable behind the billing adapter;
- the migration can coexist with named-user pilot accounts.

### Costs

- membership and entitlement resolution become a required dependency in more
  request paths;
- tests must cover cross-organization isolation and owner transfer;
- the existing user-level pricing UI cannot claim team billing until the
  organization path is implemented and Stripe test-mode evidence exists.

## Non-goals

- tax, invoices, refunds, disputes, and accounting export;
- SSO/SCIM and enterprise identity federation;
- automatic mid-cycle Stripe seat adjustment;
- making organization or billing administration available to the Agent;
- changing project-level roles or Team behavior beyond membership validation.

## Rollout gates

1. Add membership model and backfill with migration tests. Complete.
2. Add centralized organization entitlement resolution with legacy fallback. Complete.
3. Move quotas and project limits to the resolver; prove tenant isolation. Complete.
4. Add organization-scoped Stripe Checkout metadata and webhook reconciliation.
   Complete in code; real Stripe Test Mode evidence remains required.
5. Configure Stripe test-mode seat prices and retain checkout, portal, duplicate,
   out-of-order, cancellation, and capacity-change evidence.
6. Remove legacy user-subscription fallback only after an operator-reviewed data
   migration and a published customer migration policy.

## Follow-on decision

Personal-workspace provisioning and safe collaboration offboarding are governed
by ADR 0008. They are deliberately separate from Stripe reconciliation: a
member's valid active workspace and access revocation must never depend on a
payment-provider callback.
