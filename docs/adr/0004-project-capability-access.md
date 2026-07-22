# ADR 0004: Project Capability Access Model

- Status: Accepted
- Date: 2026-07-14

## Context

Organization membership is currently the only durable access boundary. That makes every active organization member able to reach every project in that organization, even when a bid should be limited to a smaller response team. Existing `Team` records describe groups but do not grant project access, and several resource APIs still trust an unscoped identifier.

This is incompatible with the BidPilot promise of governed collaboration, reviewer accountability, and Agent approval boundaries.

## Decision

1. Add a durable `ProjectMember` relation between `Project` and `User`.
2. Use the following project roles:
   - `owner`: project lifecycle, member administration, destructive actions, and all work capabilities;
   - `manager`: coordinate work, assignments, workflow execution, and exports;
   - `contributor`: read project data, upload evidence, edit requirements, and run permitted drafting work;
   - `reviewer`: read project data and perform evidence/claim/decision review actions;
   - `viewer`: read-only access.
3. Organization administrators retain an administrative bypass. They are not required to hold an explicit member row; mutating actions remain subject to their normal audit records.
4. Capabilities, rather than raw roles, gate routes and Agent tools. The first stable capability set is:
   - `project.read`
   - `project.manage`
   - `project.delete`
   - `project.members.manage`
   - `requirements.write`
   - `requirements.assign`
   - `requirements.review`
   - `bundles.write`
   - `workflow.run`
   - `review.write`
   - `deliverables.export`
5. A caller outside a project receives `404` to avoid leaking the project’s existence. A project member without the requested capability receives `403`.
6. Project creation creates an `owner` membership for the creating user in the same transaction as the project. The migration backfills current active organization administrators as `owner` and current active organization members as `contributor` for existing projects, preserving existing access while making it explicit and editable. A historical project whose organization has no active user cannot be assigned a member by migration; it remains inaccessible until an organization administrator creates or restores a user.
7. All project-scoped HTTP routes and Agent capabilities must resolve access through the same service. No route or tool may rely only on a project id, section id, bundle id, run id, or organization id.
8. Database row-level security is a later defense-in-depth phase. The application capability service is the immediate enforcement boundary and must have cross-role tests before RLS is added.

## Capability Matrix

| Capability | Owner | Manager | Contributor | Reviewer | Viewer | Org admin |
| --- | --- | --- | --- | --- | --- | --- |
| `project.read` | yes | yes | yes | yes | yes | yes |
| `project.manage` | yes | yes | no | no | no | yes |
| `project.delete` | yes | no | no | no | no | yes |
| `project.members.manage` | yes | no | no | no | no | yes |
| `requirements.write` | yes | yes | yes | no | no | yes |
| `requirements.assign` | yes | yes | no | no | no | yes |
| `requirements.review` | yes | yes | no | yes | no | yes |
| `bundles.write` | yes | yes | yes | no | no | yes |
| `workflow.run` | yes | yes | yes | no | no | yes |
| `review.write` | yes | yes | no | yes | no | yes |
| `deliverables.export` | yes | yes | no | yes | no | yes |

## Consequences

- A bid manager can restrict a sensitive response to the actual response team without creating a second organization.
- Requirement assignment and reviewer actions become attributable to a project role, not merely an organization account.
- A requirement owner or reviewer must be an active member capable of that responsibility, unless the assignee is an organization administrator using the documented administrative bypass. This prevents assigning work to a user who cannot open the bid workspace.
- The Agent can evaluate a capability before planning or invoking a tool, keeping approval modes from becoming permission escalation.
- Project deletion is a soft delete. This keeps immutable audit and provenance records referentially valid and ensures older repository helpers cannot revive a deleted project through a raw primary-key lookup.
- Existing projects remain usable after migration, but administrators should review their inherited memberships before treating the project as restricted. Disabled accounts are intentionally excluded from inherited memberships.
- The project workspace now includes member management. PostgreSQL row-level security, invitation flows, SCIM provisioning, and a formal break-glass workflow remain separate deliverables and must not be implied as already complete by this ADR.
