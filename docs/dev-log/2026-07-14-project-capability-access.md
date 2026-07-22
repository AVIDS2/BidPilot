# Project Capability Access: Delivery Log

- Date: 2026-07-14
- Scope: collaboration and authorization foundation for BidPilot projects
- Status: complete and verified locally; not deployed or committed in this phase

## Why This Was Needed

Organization membership was previously the practical access boundary. That is insufficient for a real bid team: a legal reviewer, solution architect, and bid manager may work in the same organization but should not automatically access every response workspace.

The implementation makes the project the durable collaboration boundary. It is deliberately separate from Agent approval: a model confirmation may request consent for a permitted action, but it can never confer an absent project capability.

## Delivered Design

1. `ProjectMember` records explicit roles: `owner`, `manager`, `contributor`, `reviewer`, and `viewer`.
2. `app.access.service` resolves a project once and maps roles to named capabilities.
3. The resolver returns `404` for a caller without project membership and `403` for an insufficient capability.
4. Organization administrators retain a documented administrative bypass. Mutating actions continue to create normal audit records.
5. New projects add the creator as `owner` in the same transaction.
6. Project deletion is soft deletion, preserving audit/provenance foreign-key history. All standard project reads hide deleted projects.
7. Requirement owners and reviewers must be active project members capable of their assigned responsibility, except for the explicit organization-admin bypass.
8. Child-resource routes and Agent tools resolve their parent project before acting, preventing an id from another project from becoming a bypass.
9. The project workspace exposes localized member management for people with `project.members.manage`; the server remains the source of truth for every mutation.

## Verification Evidence

Targeted verification completed during implementation:

```powershell
uv run --directory services/api pytest tests/access/test_project_member_migration.py tests/access/test_access_service.py tests/projects/test_project_members_api.py -q
# 19 passed

uv run --directory services/api pytest tests/access/test_requirement_readiness_capabilities.py tests/projects/test_project_members_api.py -q
# 6 passed

pnpm --filter @docpilot/web test -- --run src/features/projects/tabs/project-access-tab.test.tsx src/features/projects/tabs/requirements-tab.test.tsx
# 9 passed

pnpm --filter @docpilot/web build
# passed (existing Vite chunk-size warning only)
```

The local disposable migration database was also downgraded from this revision to its predecessor and upgraded back to head successfully. No VPS or production database was contacted.

Final verification after the review fixes:

```powershell
uv run --directory services/api pytest -q
# 332 passed

pnpm --filter @docpilot/web test -- --run
# 21 files, 78 tests passed

pnpm --filter @docpilot/web build
# passed (existing Vite chunk-size warning only)
```

## Independent Review

A read-only Claude review checked the project access diff for IDOR, cross-tenant paths, approval replay, child-resource access, migration behavior, and audit gaps. It found that three requirement repository queries did not independently filter soft-deleted projects. The route layer already prevented exposure, but the repository layer was hardened and a direct regression test was added.

The review also noted three deliberately deferred items: project-template creation is not yet one atomic operation, requirement status values are not yet constrained to a formal lifecycle enum, and database RLS/rate limits remain later defense-in-depth work. None creates a current project-access bypass; each is recorded for the corresponding runtime or Requirement Ledger phase.

## Accepted Limits

- PostgreSQL RLS is not enabled yet. The application capability resolver is the current enforcement boundary.
- Legacy projects receive memberships only for active existing users. Organizations without active users remain intentionally inaccessible after migration.
- Invitations, SCIM provisioning, formal break-glass access, and organization-wide policy administration are future work.
- The current LangGraph assistant wrapper still has a separate confirmation flow from the deterministic assistant runtime. Unifying their policy, durable approval, trace, and recovery contracts is the next Agent-runtime phase.

## Interview Explanation

"We started with organization-wide membership, then discovered that it could not represent a real bid response team. I added explicit project membership and mapped roles to capabilities so API routes and Agent tools share the same authorization decision. We return 404 for non-members to reduce IDOR discovery, retain soft-deleted records for auditability, and treat approval as a second step after authorization rather than a source of permission."
