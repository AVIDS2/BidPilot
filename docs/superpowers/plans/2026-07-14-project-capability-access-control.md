# Project Capability Access Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace organization-wide implicit project access with durable project memberships and capability-based enforcement across BidPilot APIs and Agent tools.

**Architecture:** `ProjectMember` stores explicit project roles; a small authorization service resolves a project and evaluates a named capability. HTTP routes and Agent tools call that service before reading or changing project-scoped data. Organization admins are a documented administrative bypass, while all other users require a membership row.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL, React, TanStack Query, Vitest, pytest.

---

## Scope and Non-Goals

- This plan protects all project-scoped resource paths; it does not add PostgreSQL RLS yet.
- Existing team groups remain available but do not silently grant project access.
- The first UI exposes project members in a compact project access surface. Organization invitations, SCIM, and enterprise SSO are separate work.
- The policy service is reused by the later unified Agent capability registry. It is not a second Agent runtime.

## File Map

- `packages/contracts/models.py`: durable `ProjectMember` relation and model associations.
- `services/api/alembic/versions/`: migration and deterministic legacy membership backfill.
- `services/api/app/access/`: role matrix, access resolution, and capability checks.
- `services/api/app/projects/`: project CRUD plus member-management APIs.
- `services/api/app/{bundles,drafting,requirements,readiness,review}/`: project-resource capability gates.
- `services/api/app/assistant/tools.py`: capability-aware project lookup and tool execution.
- `services/api/tests/access/`, `tests/projects/`, `tests/requirements/`, and affected route tests: cross-role acceptance tests.
- `apps/web/src/features/projects/`: project access panel and query invalidation.
- `apps/web/src/lib/api.ts`: project member contracts and API calls.
- `apps/web/public/locales/{en,zh-CN}/projects.json`: localized project-access labels.

### Task 1: Add Failing Role-Matrix Tests

**Files:**
- Create: `services/api/tests/access/test_project_capabilities.py`
- Modify: `services/api/tests/projects/test_create_project.py`

- [x] **Step 1: Define test fixtures for one org, one project, an owner, manager, contributor, reviewer, viewer, organization admin, and a second-organization outsider.**

```python
def test_non_member_cannot_discover_project(client, member_token, project_id):
    response = client.get(f"/projects/{project_id}", headers=member_token)
    assert response.status_code == 404

def test_reviewer_cannot_assign(client, reviewer_headers, reviewer_requirement):
    response = client.post(
        "/requirements/bulk-assign",
        json={
            "requirement_ids": [reviewer_requirement["id"]],
            "lock_versions": {reviewer_requirement["id"]: reviewer_requirement["lock_version"]},
            "owner_user_id": reviewer_requirement["owner_id"],
        },
        headers=reviewer_headers,
    )
    assert response.status_code == 403
```

- [x] **Step 2: Cover every capability row in ADR 0004 at least once, including organization-admin bypass and project-owner deletion.**
- [x] **Step 3: Run the new test file before implementation.**

```powershell
$env:DOCPILOT_DATABASE_URL='postgresql+psycopg://docpilot:docpilot@localhost:5433/docpilot_migration_test'
uv run --directory services/api pytest tests/access/test_project_capabilities.py -q
```

Expected: fail because `ProjectMember` and capability checks do not exist.

### Task 2: Add ProjectMember Model and Safe Migration

**Files:**
- Modify: `packages/contracts/models.py`
- Create: `services/api/alembic/versions/d7e8f9a0b1c2_add_project_member_access.py`
- Create: `services/api/tests/access/test_project_member_migration.py`

- [x] **Step 1: Write migration tests that upgrade a database with projects and users, then assert every existing project has explicit memberships.**
- [x] **Step 2: Add the model.**

```python
class ProjectMember(Base):
    __tablename__ = "project_member"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="contributor")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_member_project_user"),)
```

- [x] **Step 3: Use Alembic Python rows and `uuid.uuid4()` for backfill ids; do not assume a database UUID extension. Map org admins to `owner`, others to `contributor`.**
- [x] **Step 4: Upgrade and downgrade a disposable migration database.**

```powershell
uv run --directory services/api alembic upgrade head
uv run --directory services/api pytest tests/access/test_project_member_migration.py -q
```

Expected: migration is idempotent for existing rows; every project in an organization with at least one user receives inherited access. Projects in an organization with no users remain intentionally inaccessible and are reported as migration anomalies.

### Task 3: Implement One Capability Resolver

**Files:**
- Create: `services/api/app/access/__init__.py`
- Create: `services/api/app/access/service.py`
- Create: `services/api/app/access/schemas.py`
- Create: `services/api/tests/access/test_access_service.py`

- [x] **Step 1: Write unit tests for `resolve_project_access` and `require_project_capability`.**
- [x] **Step 2: Define one role-to-capability mapping from ADR 0004; do not duplicate it in routers or tools.**
- [x] **Step 3: Return a typed access result containing `project`, effective role, membership id when present, and admin-bypass flag.**
- [x] **Step 4: Raise 404 for no organization/project membership and 403 for insufficient capability.**
- [x] **Step 5: Run the unit tests.**

```powershell
uv run --directory services/api pytest tests/access/test_access_service.py -q
```

Expected: all role/capability combinations match ADR 0004 exactly.

### Task 4: Secure Project CRUD and Membership Administration

**Files:**
- Modify: `services/api/app/projects/schemas.py`
- Modify: `services/api/app/projects/repository.py`
- Modify: `services/api/app/projects/service.py`
- Modify: `services/api/app/projects/router.py`
- Modify: `services/api/tests/projects/test_create_project.py`
- Create: `services/api/tests/projects/test_project_members_api.py`

- [x] **Step 1: Change project creation to create the `owner` member in the same database transaction.**
- [x] **Step 2: Make project list and get queries capability-aware; non-admin users only see their member projects.**
- [x] **Step 3: Add `GET`, `POST`, `PATCH`, and `DELETE /projects/{project_id}/members` with `project.members.manage` enforcement.**
- [x] **Step 4: Gate status updates with `project.manage` and deletion with `project.delete`.**
- [x] **Step 5: Audit membership add/change/remove and reject cross-organization users.**
- [x] **Step 6: Run route tests.**

```powershell
uv run --directory services/api pytest tests/projects/test_create_project.py tests/projects/test_project_members_api.py -q
```

Expected: new projects are private to their owner until a member is added; admins can recover/manage them.

### Task 5: Secure Requirement and Readiness Controls

**Files:**
- Modify: `services/api/app/requirements/router.py`
- Modify: `services/api/app/requirements/service.py`
- Modify: `services/api/app/readiness/router.py`
- Modify: `services/api/app/readiness/service.py`
- Modify: `services/api/tests/requirements/test_requirement_ledger_api.py`
- Modify: `services/api/tests/readiness/test_readiness_summary.py`

- [x] **Step 1: Require `requirements.read` for list/detail, `requirements.write` for creation and regular edits, `requirements.assign` for owner/reviewer changes and bulk assignment, and `requirements.review` for evidence/claim/decision verification.**
- [x] **Step 2: Require `requirements.read` for readiness summary/download and `deliverables.export` for pack generation.**
- [x] **Step 3: Preserve optimistic locking and ownership validation after permission checks.**
- [x] **Step 4: Add cross-role acceptance cases for contributor, reviewer, viewer, and manager.**
- [x] **Step 5: Run affected tests.**

```powershell
uv run --directory services/api pytest tests/requirements tests/readiness tests/access/test_project_capabilities.py -q
```

Expected: no organization member can assign, verify, or export outside their project capability.

### Task 6: Close Unscoped Resource Routes and Agent Tools

**Files:**
- Modify: `services/api/app/bundles/router.py`
- Modify: `services/api/app/bundles/service.py`
- Modify: `services/api/app/drafting/router.py`
- Modify: `services/api/app/drafting/service.py`
- Modify: `services/api/app/review/router.py`
- Modify: `services/api/app/review/service.py`
- Modify: `services/api/app/assistant/tools.py`
- Modify: affected repository functions only where a project must be resolved from a child id
- Add tests under `services/api/tests/access/`

- [x] **Step 1: Resolve a bundle, section, thread, or run to its project before performing work, then require the matching capability.**
- [x] **Step 2: Add authentication to all list, stream, resume, and review routes that currently omit it.**
- [x] **Step 3: Make assistant project search list only accessible projects and route every project tool through the same resolver.**
- [x] **Step 4: Keep Agent approval policy separate from permission: approval never grants a missing capability.**
- [x] **Step 5: Run all directly affected API and assistant tests.**

```powershell
uv run --directory services/api pytest tests/bundles tests/drafting tests/review tests/assistant tests/access -q
```

Expected: an identifier obtained from another project or organization cannot be used through conventional routes or the Agent.

### Task 7: Add the Project Access UI

**Files:**
- Create: `apps/web/src/features/projects/tabs/project-access-tab.tsx`
- Modify: `apps/web/src/features/projects/project-detail-page.tsx`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/public/locales/en/projects.json`
- Modify: `apps/web/public/locales/zh-CN/projects.json`
- Create: `apps/web/src/features/projects/tabs/project-access-tab.test.tsx`

- [x] **Step 1: Add API contracts for project members without exposing secrets or unrelated organization member data.**
- [x] **Step 2: Render a compact access table with member name, role, inherited/admin status, role selector, and remove action.**
- [x] **Step 3: Show the surface only to `project.members.manage`; viewers and contributors see no deceptive controls.**
- [x] **Step 4: Await TanStack Query invalidation after every membership mutation.**
- [x] **Step 5: Test role change/remove, denied states, long names, Chinese labels, and mobile overflow.**

```powershell
pnpm --filter @docpilot/web test -- --run src/features/projects/tabs/project-access-tab.test.tsx
pnpm --filter @docpilot/web build
```

Expected: a bid owner can add a reviewer and constrain access without leaving the project workspace.

### Task 8: Verification, Security Review, and Learning Record

**Files:**
- Modify: `progress.txt`
- Create: `docs/dev-log/2026-07-14-project-capability-access.md`
- Update: `docs/superpowers/specs/2026-07-14-bidpilot-product-agent-refoundation-v2-design.md` only if an accepted decision differs from its current access section

- [x] **Step 1: Run API tests, web tests, production build, migration upgrade, migration downgrade, and `git diff --check`.**
- [x] **Step 2: Perform an independent review focused on direct-object-reference access, cross-tenant membership, audit coverage, Agent tool bypasses, and stale role caches.**
- [x] **Step 3: Record accepted limitations: no RLS yet, organization admin bypass, legacy membership backfill behavior, and future invitation/SCIM work.**
- [x] **Step 4: Add an interview note explaining RBAC versus ABAC, capability checks, IDOR prevention, and why approval is not authorization.**

Expected: every project-scoped entry point has a testable authorization decision and the product makes no unsupported enterprise-security claim.
