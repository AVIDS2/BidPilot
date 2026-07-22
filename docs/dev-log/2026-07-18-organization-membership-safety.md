# 2026-07-18: Organization membership safety and test database isolation

## Problem found

The prior organization switch implementation rewrote `User.org_id` with no
membership record. This was not a valid multi-organization model: a user could
be switched into any existing organization, and a later team/seat implementation
would have no durable way to prove access.

During implementation, a local release rehearsal also revealed that API tests
were using the default development database when no CI database URL was set.
That made local test artifacts unreliable and accumulated fixture data in the
development workspace.

## Implemented behavior

- Added `OrganizationMembership` with active/removed state and owner/admin/member
  roles.
- Added an Alembic migration that backfills each existing user into its current
  organization. The earliest enabled account in each organization becomes the
  deterministic initial owner; no global platform-admin role is inferred as a
  billing role.
- Organization listing and member listing now use active membership rows.
- Organization switching refuses a non-member before it mutates the active
  context. Creating an organization creates an owner membership and switches
  inside one transaction.
- Registration, bootstrap-admin creation, and invitation acceptance create the
  membership in the same transaction as their identity change.
- Added a test-only database safety boundary. API pytest and the local release
  rehearsal accept only `DOCPILOT_TEST_DATABASE_URL`, or an application database
  whose name already ends in `_test`.
- Added `scripts/prepare_local_test_database.py`; it only creates a local
  PostgreSQL database with an `_test` suffix and never prints a connection URL.

## Verification

- Applied the organization-membership migration to the existing local database
  and to a freshly created `docpilot_test` database from an empty Alembic state.
- Focused organization, invitation, bootstrap, test-safety, and rehearsal tests:
  `26 passed` on the isolated test database.
- Relevant API and script Ruff checks passed.
- Full release rehearsal on the isolated database: API `530 passed`, Worker
  `78 passed`, frontend TypeScript check, `25` Vitest files / `89` tests, and
  production Vite build all passed.
- `alembic check` still reports pre-existing checkpoint/index metadata drift,
  but does not report the new organization-membership table as a missing
  migration.
- A read-only Claude Code review was attempted but its CLI request timed out
  after 244 seconds with no review result; it is not counted as external review
  approval.

## Follow-up: organization entitlement foundation

- Added `OrganizationSubscription` with one workspace-scoped plan/status,
  seat-capacity snapshot, billing owner, and future Stripe reconciliation
  identifiers. No legacy subscriptions were deleted or rewritten.
- Added one entitlement resolver that first proves active membership, then
  prefers an organization subscription, otherwise permits a legacy user
  subscription only for that user's selected organization. Inactive paid
  statuses normalize to Starter before any limit decision.
- Project limits and official workflow, Assistant, and indexing quota checks
  now resolve through the workspace. Usage events retain the actor but are
  aggregated by `org_id`, so members share a purchased allowance and the same
  user remains isolated between separate organizations.
- Added the read-only `GET /organizations/current/entitlements` API for a
  workspace/account UI. It exposes no Stripe secret or payment data.
- The anonymous local development fallback remains server-only and is disabled
  whenever production authentication is enabled; it never weakens production
  entitlement checks.

### Follow-up verification

- Applied `e5f6a7b8c9d0_add_organization_subscriptions` successfully to the
  dedicated local `docpilot_test` database.
- New entitlement isolation and precedence coverage plus related focused API
  coverage passed: `43 passed`.
- Full API regression on the dedicated test database passed: `540 passed`.
- Stripe organization Checkout metadata and subscription-item quantity
  reconciliation remain intentionally pending.

## Follow-up: seat capacity and invitation governance

- New workspaces and explicit organization registration now create a managed
  Starter subscription with a single seat. Existing legacy workspaces retain a
  compatibility path until their billing state is migrated.
- The central membership command locks the organization row before checking
  capacity, so direct membership creation, reactivation, and invitation
  acceptance cannot independently overbook a workspace.
- Invitation creation and revocation require an active workspace `owner` or
  `admin`; accepting a pending invitation also verifies that the authenticated
  email matches the invited email. A failed capacity check leaves the invitation
  pending rather than silently consuming a seat.
- The account page now consumes the read-only workspace entitlement endpoint to
  show the plan, seat usage, remaining capacity, and billing-owner status. It
  intentionally provides no browser-side billing or seat mutation.

### Follow-up verification

- Focused entitlement and invitation coverage passed: `27 passed`.
- Full API regression on the dedicated test database passed: `545 passed`.
- Account-page Vitest coverage and the production web build both passed.

## Follow-up: organization Stripe reconciliation

- Checkout now starts only for the active workspace billing owner and writes
  `org_id`, billing-owner identity, and plan metadata to both the Checkout
  Session and resulting Stripe Subscription.
- A checkout begins with the current active-member count as its licensed seat
  quantity. Existing user-level Stripe customers are deliberately not attached
  to a workspace automatically; their migration must be reviewed by an
  operator.
- Signed webhook resolution prefers local workspace subscription/customer IDs,
  validates supplied metadata against the local organization and active billing
  owner, and never creates a workspace subscription from Stripe metadata alone.
- A single Subscription item's quantity is persisted as both the billable seat
  count and workspace capacity. A lower external quantity blocks new members;
  it never silently removes current members. The account view derives and
  displays the resulting seat-overage count for the billing owner.
- Stripe receipt records now retain an optional local organization identifier in
  addition to their existing safe customer/subscription correlations. Raw
  Stripe payloads remain intentionally unstored.
- Added a Test Mode-only read-only preflight script and evidence runbook. The
  local environment has no Stripe credentials, so no live/Test Mode claim is
  made and no real Stripe API operation was executed during implementation.

### Follow-up verification

- Applied `f6a7b8c9d0e1_add_stripe_receipt_organization_mapping` to the
  dedicated local test database.
- Stripe adapter, billing route, webhook, entitlement, invitation, and
  preflight coverage passed: `44 passed` then `27 passed` for the expanded
  preflight suite.
- Full API regression passed: `551 passed`; the production web build passed.
- `alembic check` continues to report pre-existing metadata/index drift outside
  the organization Stripe migration. It did not report the new receipt mapping
  as an unversioned schema change.

## Follow-up: workspace-scoped invitation authority

- The collaboration entry is now visible to every workspace member rather than
  being hidden behind the unrelated global platform-admin role.
- Invitation management resolves the caller's active `OrganizationMembership`
  and enables invitation actions only for workspace `owner` and `admin` roles.
  Regular members do not make a doomed invitation-list request.
- The organization member response now includes the server-derived email and
  workspace role needed for this authorization decision. The browser never
  infers a workspace role from the global user record.

### Follow-up verification

- Focused organization entitlement and invitation coverage passed on the
  dedicated test database (`22 passed`).
- The production web build and focused invitation-page behavior coverage passed.

## Follow-up: personal workspaces, safe offboarding, and account deletion

- Standalone registration now creates a dedicated `personal` workspace and a
  Starter organization subscription. Invitation registration continues to join
  the invited `team` workspace and does not create a redundant personal one.
- Workspace owners can change member roles, transfer billing responsibility to
  another active owner, and remove members. Removal is one transaction: it
  rejects final-owner and billing-owner loss, revokes project/team grants,
  transfers a sole project ownership to the removing manager, switches or
  provisions the removed user's fallback workspace, and writes a dedicated
  organization membership event.
- The platform user directory remains global for platform administrators;
  workspace-scoped collaboration uses the organization member API instead.
  This restored administrative visibility for standalone registrations without
  weakening workspace data isolation.
- Self-service account deletion now protects organizational assets before
  deleting anything. Team owners, team billing owners, sole project owners,
  non-empty personal workspaces, and paid personal subscriptions must be
  resolved first. A free empty personal workspace and its subscription are
  deleted atomically with the account. A remaining undeclared dependency is
  surfaced as a safe conflict rather than a raw database constraint error.

### Follow-up verification

- Applied `f7a8b9c0d1e2_add_personal_workspaces_and_membership_events` to the
  dedicated `docpilot_test` database.
- Registration, email verification, user management, invitations, organization
  governance, and account-deletion guard coverage passed: `46 passed`.
- Full API regression passed: `567 passed`.
- Worker regression passed: `78 passed`.
- Relevant API Ruff checks and the frontend production Vite build passed.
