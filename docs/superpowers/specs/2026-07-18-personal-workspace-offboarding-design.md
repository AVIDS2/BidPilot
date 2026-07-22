# Personal Workspace and Offboarding Design

## Product outcome

BidPilot treats a workspace as the user's current operating context. A person
can collaborate in many team workspaces, but they always retain one valid
landing workspace. This eliminates two prototype-era failure modes:

- unrelated self-registered users sharing a default tenant; and
- an offboarded user retaining an invalid active-workspace pointer.

## Workspace types

| Type | Created by | Purpose | Commercial rule |
| --- | --- | --- | --- |
| `personal` | standalone registration or safe offboarding fallback | private landing and recovery context | Starter-only baseline; not a bypass for team capacity |
| `team` | explicit workspace creation or existing customer data | shared projects, seats, quotas, billing | active members consume the organization seat capacity |

The legacy `default` workspace is classified as a team workspace for
compatibility. It is no longer used for new standalone registration.

## Lifecycle flows

### Standalone registration

1. Generate a stable user identifier before persistence.
2. Create a `personal` organization using a non-PII deterministic slug derived
   from that identifier.
3. Persist the user with that organization as active context.
4. Create its owner membership and managed Starter subscription in the same
   transaction.

### Invitation registration

1. Verify the invitation token and normalized email before creating the user.
2. Persist the user directly in the inviting team workspace.
3. Create the member membership only after the shared seat-capacity check.
4. Do not create a redundant personal workspace in this path. If the member is
   later offboarded, the offboarding command provisions one only when necessary.

### Member offboarding

The workspace manager explicitly removes a member. The server performs all
state changes atomically:

```text
authorize manager
  -> validate owner and billing-owner invariants
  -> select existing fallback workspace or create personal fallback
  -> transfer any sole-owned project to the removing manager
  -> revoke team and project memberships in source workspace
  -> switch active context if needed
  -> mark organization membership removed
  -> persist organization audit event
```

The API returns whether a fallback workspace was created so the UI can state the
outcome without inventing it client-side.

## Role matrix

| Action | Member | Admin | Owner | Billing owner |
| --- | --- | --- | --- | --- |
| view members | yes | yes | yes | yes |
| invite/revoke invite | no | yes | yes | yes |
| remove member/admin | no | yes | yes | yes |
| remove owner | no | no | yes, if another owner remains | yes, if another owner remains |
| change member roles | no | no | yes | yes |
| transfer billing ownership | no | no | no unless current billing owner | yes |
| start Checkout/Billing Portal | no | no | only if also billing owner | yes |

## Failure modes

| Condition | Required behavior |
| --- | --- |
| caller lacks active workspace manager role | 403 before reads that disclose membership state |
| target is final owner | 409, no mutation |
| target is current billing owner | 409, require explicit transfer first |
| target is sole project owner | transfer ownership to the explicit removing manager; self-removal requires a different owner first |
| fallback workspace creation fails | transaction rolls back; source member remains active |
| stale project/team grants remain | source grants are removed in the transaction |
| concurrent seat change/offboarding | workspace/member rows are locked during command execution |

## Verification

Backend tests cover standalone versus invited registration, personal fallback
provisioning, explicit existing-workspace fallback, role restrictions,
last-owner/billing-owner protection, project-owner handoff, grant revocation,
and audit persistence.
Frontend tests cover only server-returned member state and management controls;
the browser does not infer commercial or role policy.

## Rollout

1. Add workspace type and organization-membership event migration.
2. Change new standalone registration only; preserve legacy default data.
3. Enable the offboarding API and workspace management controls.
4. Produce a reviewed default-workspace migration inventory before any project
   movement or bulk reassignment.
