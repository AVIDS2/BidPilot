# ADR 0008: Personal Workspaces and Safe Member Offboarding

- Status: Accepted
- Date: 2026-07-18

## Context

`OrganizationMembership` makes a user eligible to access one or more customer
workspaces, while `User.org_id` remains the user's active-workspace pointer.
The original registration fallback puts unrelated accounts into one shared
`Default Organization`. That is convenient for a prototype but unsafe for a
multi-tenant product: unrelated users can share an organization boundary before
they have explicitly collaborated.

Seat-overage remediation needs an owner to remove members. A naive soft-delete
of the last active membership would leave `User.org_id` pointing at a workspace
the user no longer belongs to. It would also leave stale project and team
memberships visible in collaboration views. This is an authorization and
recovery problem, not merely a UI problem.

## Decision

### 1. Every new standalone account receives a personal workspace

New registration without a valid invitation creates a `personal` workspace and
makes the account its owner. A valid invitation remains the only registration
path that directly joins an existing `team` workspace. Explicit workspace
creation creates a `team` workspace.

Personal workspaces are a safety and recovery boundary, not a second billing
product. They receive Starter entitlements and are not a way to bypass a team's
paid seat count or shared quota.

### 2. The legacy default workspace is not silently repartitioned

Existing records in `Default Organization` may contain real shared projects.
The platform must not infer ownership from a user row and move projects into
new workspaces automatically. New registrations stop using the default
workspace; existing default-workspace migration requires an operator-reviewed
export, ownership decision, and retained audit evidence.

### 3. Member removal is one transactional command

The command must, in one database transaction:

1. authorize the acting workspace manager;
2. reject removal of the last owner;
3. reject removal or demotion of the billing owner until billing ownership is
   explicitly transferred;
4. transfer every project for which the target is the sole owner to the explicit
   removing manager; self-removal with a sole-owned project is rejected until
   another owner is assigned;
5. revoke project and team memberships in the source workspace;
6. move the removed user's active context to another active workspace, preferring
   a personal workspace; or provision a personal workspace if none exists;
7. mark the source organization membership `removed`; and
8. write an organization-level membership audit event with actor, target, event,
   and safe outcome metadata.

No background job, browser callback, or Stripe webhook is allowed to perform a
partial version of this state transition.

### 4. Ownership and billing ownership are distinct controls

Only an active workspace owner may change organization member roles. The final
owner may not be demoted or removed. Only the current billing owner may transfer
billing ownership, and the recipient must already be an active owner. Transfer
does not change a Stripe customer by itself; it changes the local authority
that may start a Checkout or Billing Portal session.

### 5. Audit and recovery are first-class behavior

Organization-level collaboration actions use a dedicated immutable event ledger
rather than overloading project audit events. The event records stable local
identifiers and outcome metadata only; it never stores credentials, payment
data, or raw provider payloads.

## Consequences

### Positive

- standalone users no longer start in a shared tenant;
- seat remediation can safely reduce active membership without stranding an
  account;
- removal immediately revokes collaboration visibility while preserving project
  business history;
- financial authority remains explicit and reviewable.

### Costs

- registration and member offboarding require additional transactional tests;
- legacy default-workspace data needs a deliberate migration runbook;
- a user may receive an empty personal workspace after offboarding, which the
  UI must explain rather than presenting as an error.

## Non-goals

- arbitrary project-owner selection during offboarding; the removing manager is
  the only deterministic fallback in the first release;
- SCIM, SSO lifecycle automation, or just-in-time provisioning;
- automatic Stripe proration or seat-quantity adjustment;
- Agent authority over organization membership or billing ownership.

## Acceptance evidence

- standalone registration produces a unique personal workspace and one active
  owner membership;
- invited registration joins the intended team workspace and does not create an
  unnecessary personal workspace;
- removing a member revokes project/team membership and leaves the user with a
  valid active workspace;
- last-owner and billing-owner removal paths are rejected before mutation;
- role/billing transfers and member removal emit organization audit events;
- existing `Default Organization` records remain unchanged by the migration.
