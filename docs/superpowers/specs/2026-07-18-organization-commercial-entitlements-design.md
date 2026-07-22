# Organization Commercial Entitlements Design

## Objective

Move BidPilot from a user-plan prototype to a team-safe commercial model without
breaking existing named-user pilot accounts. The first deliverable is not a new
pricing screen. It is a durable organization membership and entitlement boundary
that every paid capability can rely on.

## Product contract

For a customer organization:

1. An owner creates or accepts a workspace.
2. The workspace has a plan and a finite number of paid seats.
3. Owners invite members only while seat capacity is available.
4. Members work on explicitly shared projects, but their official-provider use
   consumes the workspace allowance, not a hidden personal allowance.
5. A user who belongs to multiple organizations must actively select one; data,
   project visibility, quota, and billing never cross that boundary.
6. Only an owner can make a payment or change billing.

## Existing constraints

- `Project.org_id`, `UsageEvent.org_id`, and most runtime events already carry
  organization scope.
- `User.org_id` is currently a required compatibility field and is used as the
  active context.
- `Subscription` is currently one-to-one with `User`.
- existing Stripe webhook receipt handling is user-subscription based but
  already has signature verification, durable event-id deduplication, and
  stale-event protection.
- legacy data must keep working through a controlled fallback, not by guessing
  billing ownership.

## Domain model

```text
User --< OrganizationMembership >-- Organization --1 OrganizationSubscription
  |                                      |
  |                                      +--< Project --< ProjectMember >-- User
  +--< UsageEvent (actor)                +--< UsageEvent (commercial scope)
```

### OrganizationMembership

| Field | Meaning |
| --- | --- |
| `org_id`, `user_id` | stable membership identity |
| `role` | `owner`, `admin`, `member` |
| `status` | `active` or `removed` |
| `joined_at`, `removed_at` | lifecycle/audit times |
| `created_by_user_id`, `updated_by_user_id` | responsible actor |

Invariants:

- an active organization has at least one active owner;
- a removed member cannot switch to, enumerate, or access that organization;
- invitation acceptance activates a membership only after capacity validation;
- an active member consumes one seat in the first commercial model.

### OrganizationSubscription

| Field | Meaning |
| --- | --- |
| `org_id` | one commercial entitlement record per organization |
| `plan`, `status` | normalized local entitlement state |
| `seat_limit` | purchased active-member capacity |
| `billing_owner_user_id` | active organization owner authorized to bill |
| Stripe identifiers | customer, subscription, subscription item |
| event timestamp | stale webhook protection |

The initial `seat_limit` for a Starter organization equals one. Professional and
Enterprise may use greater capacity only after a signed Stripe reconciliation or
operator-approved pilot grant.

## Entitlement resolver

Create a single service boundary:

```python
resolve_org_entitlements(db, *, org_id, actor_user_id) -> EntitlementContext
```

It must:

1. verify that the actor has active membership in `org_id`;
2. load an active `OrganizationSubscription` if present;
3. otherwise use the actor's legacy `Subscription` only for the actor's active
   organization during migration;
4. normalize canceled, unpaid, incomplete, expired, and paused paid states to
   Starter entitlements;
5. return plan, lifecycle status, seat capacity, feature flags, and limits;
6. never read plan/limit state from browser input or Agent state.

The caller owns presentation. The resolver owns authorization and commercial
truth.

## Planned implementation slices

### Slice 1: Membership safety

- Add `OrganizationMembership` plus migration/backfill.
- Make organization listing and switching membership-based.
- Require active membership in organization and team/project mutation routes.
- Add owner-last-member guards and cross-organization tests.

### Slice 2: Organization entitlement foundation

- Add `OrganizationSubscription` and a non-destructive legacy fallback.
- Add `EntitlementContext` and redirect project quota and official AI quota
  checks to organization scope.
- Expose a safe read-only entitlement summary for account/workspace UI.
- Add migration, API, and isolation tests.

**Status: implemented locally on 2026-07-18.** The resolver verifies active
membership, organization subscriptions override legacy user subscriptions, and
inactive paid statuses resolve to Starter. Project capacity and official
workflow, Assistant, and indexing quota aggregation are organization-scoped.
The legacy user subscription bridge remains active only for the user's selected
organization until the organization Stripe migration is complete.

### Slice 3: Seat capacity and invitations

- Validate active membership count before accepting an invitation.
- Add owner-only seat/capacity information in workspace settings.
- Keep automatic Stripe quantity adjustment out of this slice.

**Status: implemented locally on 2026-07-18.** New organizations receive a
managed Starter subscription with one seat. Membership creation, reactivation,
and invitation acceptance use the same locked server-side capacity gate;
over-capacity invitations remain pending. The account page reads a safe
workspace entitlement summary and distinguishes the billing owner from other
members, without exposing a browser-side billing mutation.

### Slice 4: Stripe organization reconciliation

- Change Checkout metadata from user-only to organization context.
- Add Stripe subscription-item and quantity handling.
- Map webhook receipts to organization subscription state.
- Rehearse real Stripe test mode before exposing any paid team path.

#### Reconciliation contract

1. Only the active `billing_owner_user_id` for an organization can create a
   Checkout or Customer Portal session. Browser input never supplies an
   organization, customer, price, or seat count.
2. A new Checkout session copies `org_id`, `billing_owner_user_id`, and `plan`
   into both the Checkout Session metadata and `subscription_data.metadata`.
   The Checkout Session uses the current active-member count (minimum one) as
   its initial licensed-seat quantity.
3. A webhook first resolves an existing local organization subscription by
   Stripe subscription ID or customer ID. It then verifies any supplied
   organization and billing-owner metadata against the local record and active
   owner membership. Metadata-only events are accepted only when a local
   organization subscription already exists; a webhook never creates a new
   commercial workspace.
4. For a single licensed Subscription item, Stripe's `items.data[0].quantity`
   becomes both `billable_seat_count` and `seat_limit`. Checkout completion may
   set the paid plan/status but must not grant extra seats until the subscription
   object reports its item quantity.
5. If a portal-side downgrade makes paid seats fewer than active members,
   BidPilot records Stripe's actual quantity and blocks new/reinstated members.
   It never removes users automatically. A derived `seat_overage_count` is
   surfaced to the workspace owner; an explicit owner remediation workflow is
   still required before Customer Portal quantity changes are enabled.
6. Existing user-level Stripe customers are not silently attached to an
   organization. Their migration requires an explicit operator-reviewed path.
   This avoids accidental reassignment of a historic payment relationship.

The adapter uses Stripe's documented metadata propagation: Checkout Session
metadata appears in `checkout.session.completed`, while
`subscription_data.metadata` appears on the resulting Subscription event.
The plan price must be configured in Stripe as a recurring `licensed` price so
its subscription-item quantity is a valid per-seat count.

**Status: implemented locally on 2026-07-18.** Checkout and Portal authorization
now use the active workspace billing owner. Signed webhook reconciliation maps
to a pre-existing organization subscription, records the organization on its
safe receipt, rejects mismatched owner metadata, and adopts the single Stripe
Subscription item quantity as the paid seat capacity. The retained Stripe Test
Mode rehearsal is still mandatory before this flow is enabled for customers.

## Failure handling

| Situation | Required behavior |
| --- | --- |
| user switches to an organization without membership | return 403/404; do not mutate active context |
| last owner removal | deny before write |
| invitation would exceed capacity | keep invitation pending; show capacity error |
| Stripe webhook is duplicate | return success without duplicate mutation |
| Stripe event is older than local state | retain ignored receipt; do not roll back entitlement |
| Stripe metadata does not map to valid org/owner | retain safe ignored receipt; never create entitlement |
| no org subscription exists during migration | limited legacy user fallback only; log and surface migration state |

## Acceptance evidence

- A user can belong to two organizations and switch only between memberships.
- An organization owner cannot remove or demote the last owner.
- Two active users in one organization consume shared official-provider quota.
- The same user in a second organization has isolated usage and projects.
- A canceled organization subscription grants Starter capability regardless of a
  paid browser-side value.
- A duplicate/out-of-order Stripe webhook cannot change current organization
  entitlements twice or backwards.
- A full local release rehearsal and a real Stripe test-mode evidence packet
  pass before any paid self-service claim.

## Deliberate deferrals

- automated seat quantity changes and proration;
- organization subscription transfer;
- bulk SCIM provisioning;
- storage-meter billing and overage invoices;
- public self-service Enterprise pricing;
- Agent control over organization, billing, provider keys, or infrastructure.
