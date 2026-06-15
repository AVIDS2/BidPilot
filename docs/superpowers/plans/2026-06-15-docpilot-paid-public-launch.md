# DocPilot Paid Public Launch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make DocPilot ready for paid public launch with Stripe billing, durable usage accounting, entitlement enforcement, support tooling, and customer-visible billing state.

**Architecture:** Keep the commercial control plane in the API and database. Stripe remains the payment processor, while the backend owns subscription truth, monthly usage accounting, quota checks, and admin support actions. The frontend only reflects state and forwards user actions.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, Stripe, PostgreSQL, React/Vite, pytest, Vitest, PowerShell on Windows.

---

## Scope Guard

Implement only the paid public launch scope from `docs/superpowers/specs/2026-06-15-docpilot-paid-public-launch-design.md`.

Do not implement in this plan:

- enterprise SSO/MFA;
- Kubernetes or multi-region ops;
- custom payment processor replacement;
- support desk workflow automation;
- data warehouse analytics;
- new scenario packages;
- visual workflow builder.

## Key Existing Files

- `services/api/app/billing/router.py` — Stripe checkout and webhook entrypoints.
- `services/api/app/auth/service.py` — subscription update helpers and auth state.
- `services/api/app/models.py` — subscription and usage domain models.
- `services/api/app/usage/service.py` — usage recording and quota logic.
- `services/api/app/usage/router.py` — current usage inspection endpoint.
- `services/api/app/providers/service.py` — provider config and BYOK handling.
- `services/api/app/chat/service.py` — assistant usage entrypoints if metered.
- `services/api/app/drafting/service.py` — workflow run creation and quota gate.
- `services/api/app/main.py` — route registration and middleware.
- `services/api/tests/billing/` — billing route tests.
- `services/api/tests/usage/` — usage service tests.
- `services/api/tests/providers/` — provider settings tests.
- `apps/web/src/features/pricing/` — pricing and upgrade UX.
- `apps/web/src/features/settings/` — billing/provider/account state UI.
- `docs/ops/release-checklist.md` — release gate.
- `docs/product/known-limitations.md` — launch constraints.

## Suggested Execution Order

1. Subscription truth and usage ledger.
2. Stripe checkout and webhook reconciliation.
3. Entitlement matrix and quota enforcement.
4. Billing/support admin tooling.
5. Customer-facing billing UI.
6. Docs and release checklist.
7. Final verification suite.

---

### Task 1: Add Durable Billing and Usage State

**Files:**

- Modify: `services/api/app/models.py`
- Modify: `services/api/alembic/versions/`
- Modify: `services/api/app/usage/service.py`
- Test: `services/api/tests/usage/test_usage_service.py`

- [ ] **Step 1: Write the failing usage ledger tests**

Create or extend `services/api/tests/usage/test_usage_service.py` with:

```python
def test_record_usage_event_creates_monthly_ledger_entry(db_session, user_factory, project_factory):
    user = user_factory()
    project = project_factory(org_id=user.org_id)

    event = usage_service.record_usage_event(
        db_session,
        user_id=user.id,
        org_id=user.org_id,
        project_id=project.id,
        event_type=usage_service.WORKFLOW_DRAFT_STARTED,
        provider_source=ProviderSource.OFFICIAL,
        execution_run_id="run-123",
        units=1,
    )

    assert event.event_type == usage_service.WORKFLOW_DRAFT_STARTED
    assert event.provider_source == ProviderSource.OFFICIAL
    assert event.units == 1
    assert event.project_id == project.id


def test_usage_quota_counts_official_events_only(db_session, user_factory, project_factory):
    user = user_factory()
    project = project_factory(org_id=user.org_id)

    for _ in range(3):
        usage_service.record_usage_event(
            db_session,
            user_id=user.id,
            org_id=user.org_id,
            project_id=project.id,
            event_type=usage_service.WORKFLOW_DRAFT_STARTED,
            provider_source=ProviderSource.OFFICIAL,
            execution_run_id=f"run-{_}",
            units=1,
        )

    result = usage_service.check_workflow_quota(db_session, user.id, user.org_id, ProviderSource.OFFICIAL)
    assert result.allowed is False
    assert result.limit == 3


def test_usage_quota_ignores_byok_events(db_session, user_factory, project_factory):
    user = user_factory()
    project = project_factory(org_id=user.org_id)

    for _ in range(3):
        usage_service.record_usage_event(
            db_session,
            user_id=user.id,
            org_id=user.org_id,
            project_id=project.id,
            event_type=usage_service.WORKFLOW_DRAFT_STARTED,
            provider_source=ProviderSource.BYOK,
            execution_run_id=f"run-{_}",
            units=1,
        )

    result = usage_service.check_workflow_quota(db_session, user.id, user.org_id, ProviderSource.BYOK)
    assert result.allowed is True
```

- [ ] **Step 2: Run the tests and confirm failure**

Run:

```powershell
uv run --directory services/api pytest tests/usage/test_usage_service.py -q
```

Expected:

- ledger or quota assertions fail because the monthly usage model is incomplete.

- [ ] **Step 3: Implement the ledger model and quota helpers**

Modify `services/api/app/models.py` to add a `UsageEvent` SQLAlchemy model with:

```python
class UsageEvent(Base):
    __tablename__ = "usage_event"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    org_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    project_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    provider_source: Mapped[str] = mapped_column(String, nullable=False, index=True)
    units: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    execution_run_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    period_key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
```

Modify `services/api/app/usage/service.py` to:

```python
WORKFLOW_DRAFT_STARTED = "workflow_draft_started"
WORKFLOW_DRAFT_SUCCEEDED = "workflow_draft_succeeded"
WORKFLOW_DRAFT_FAILED = "workflow_draft_failed"

def current_period_key(now: datetime | None = None) -> str:
    dt = now or datetime.now(timezone.utc)
    return dt.strftime("%Y-%m")

def record_usage_event(..., units: int = 1) -> UsageEvent:
    event = UsageEvent(...)
    db.add(event)
    db.flush()
    return event

def count_official_workflow_starts(db: Session, user_id: str, period_key: str) -> int:
    return db.scalar(
        select(func.count(UsageEvent.id))
        .where(UsageEvent.user_id == user_id)
        .where(UsageEvent.period_key == period_key)
        .where(UsageEvent.event_type == WORKFLOW_DRAFT_STARTED)
        .where(UsageEvent.provider_source == ProviderSource.OFFICIAL.value)
    ) or 0
```

Add a migration that creates the `usage_event` table and indexes the lookup fields.

- [ ] **Step 4: Verify the tests**

Run:

```powershell
uv run --directory services/api pytest tests/usage/test_usage_service.py -q
```

Expected:

- usage ledger tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/api/app/models.py services/api/app/usage/service.py services/api/alembic/versions/* services/api/tests/usage/test_usage_service.py
git commit -m "feat: add durable usage ledger"
```

### Task 2: Reconcile Stripe Checkout and Webhooks

**Files:**

- Modify: `services/api/app/billing/router.py`
- Modify: `services/api/app/auth/service.py`
- Test: `services/api/tests/billing/test_billing.py`

- [ ] **Step 1: Write failing billing tests**

Extend `services/api/tests/billing/test_billing.py` with:

```python
def test_checkout_uses_app_url(monkeypatch, client, auth_headers, mock_checkout):
    monkeypatch.setenv("DOCPILOT_APP_URL", "https://bidpilot.rglens.com")

    response = client.post("/billing/checkout?plan=professional", headers=auth_headers)

    assert response.status_code == 200
    _, kwargs = mock_checkout.call_args
    assert kwargs["success_url"] == "https://bidpilot.rglens.com/projects?checkout=success"
    assert kwargs["cancel_url"] == "https://bidpilot.rglens.com/pricing?checkout=cancelled"


def test_webhook_updates_subscription_state(db_session):
    event = {
        "type": "checkout.session.completed",
        "data": {"object": {"metadata": {"user_id": "user-123", "plan": "professional"}}},
    }
    # use a Stripe signature stub in the existing webhook helper test setup
    result = billing_service.handle_stripe_event(db_session, event)
    assert result.subscription_status == "professional"
```

- [ ] **Step 2: Run the tests and confirm failure**

Run:

```powershell
uv run --directory services/api pytest tests/billing/test_billing.py -q
```

Expected:

- checkout or webhook assertions fail because the launch behavior is not fully wired.

- [ ] **Step 3: Implement Stripe reconciliation**

Modify `services/api/app/billing/router.py` and `services/api/app/auth/service.py` so that:

```python
success_url = f"{get_app_url()}/projects?checkout=success"
cancel_url = f"{get_app_url()}/pricing?checkout=cancelled"
```

and webhook handling updates local subscription state idempotently for:

```python
checkout.session.completed
customer.subscription.updated
customer.subscription.deleted
invoice.payment_failed
```

Keep plan/state transitions explicit:

```python
trial
starter
professional
enterprise
past_due
canceled
unpaid
```

- [ ] **Step 4: Verify the tests**

Run:

```powershell
uv run --directory services/api pytest tests/billing/test_billing.py -q
```

Expected:

- billing tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/api/app/billing/router.py services/api/app/auth/service.py services/api/tests/billing/test_billing.py
git commit -m "feat: reconcile stripe billing state"
```

### Task 3: Add Plan Entitlements and Enforcement

**Files:**

- Modify: `services/api/app/usage/service.py`
- Modify: `services/api/app/providers/service.py`
- Modify: `services/api/app/drafting/service.py`
- Modify: `services/api/app/chat/service.py`
- Test: `services/api/tests/drafting/test_workflow_quota.py`
- Test: `services/api/tests/providers/test_providers_api.py`

- [ ] **Step 1: Write entitlement and quota tests**

Add:

```python
def test_starter_plan_blocks_after_monthly_workflow_limit(db_session, user_factory, project_factory):
    user = user_factory(plan="starter")
    project = project_factory(org_id=user.org_id)

    for index in range(3):
        usage_service.record_usage_event(... provider_source=ProviderSource.OFFICIAL, execution_run_id=f"run-{index}")

    result = usage_service.check_workflow_quota(db_session, user.id, user.org_id, ProviderSource.OFFICIAL)
    assert result.allowed is False


def test_professional_plan_bypasses_trial_limit(db_session, user_factory):
    user = user_factory(plan="professional")
    result = usage_service.check_workflow_quota(db_session, user.id, user.org_id, ProviderSource.OFFICIAL)
    assert result.allowed is True
```

- [ ] **Step 2: Run the tests and confirm failure**

Run:

```powershell
uv run --directory services/api pytest tests/drafting/test_workflow_quota.py tests/providers/test_providers_api.py -q
```

Expected:

- entitlement assertions fail until plan gating is implemented.

- [ ] **Step 3: Implement plan matrix checks**

Add a simple backend matrix:

```python
PLAN_ENTITLEMENTS = {
    "trial": {"max_projects": 1, "official_workflow_runs": 3, "byok_enabled": False},
    "starter": {"max_projects": 3, "official_workflow_runs": 3, "byok_enabled": True},
    "professional": {"max_projects": 20, "official_workflow_runs": None, "byok_enabled": True},
    "enterprise": {"max_projects": None, "official_workflow_runs": None, "byok_enabled": True},
}
```

Enforce the matrix in workflow and provider access helpers before any provider call.

- [ ] **Step 4: Verify the tests**

Run:

```powershell
uv run --directory services/api pytest tests/drafting/test_workflow_quota.py tests/providers/test_providers_api.py -q
```

Expected:

- quota and entitlement tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/api/app/usage/service.py services/api/app/providers/service.py services/api/app/drafting/service.py services/api/app/chat/service.py services/api/tests/drafting/test_workflow_quota.py services/api/tests/providers/test_providers_api.py
git commit -m "feat: enforce plan entitlements"
```

### Task 4: Add Billing Support Tools

**Files:**

- Modify: `services/api/app/ops/router.py` or a new support router under `services/api/app/billing/`
- Modify: `services/api/app/main.py`
- Test: `services/api/tests/` support tests

- [ ] **Step 1: Write failing support lookup tests**

Add tests for admin-only support lookup:

```python
def test_admin_can_inspect_subscription_state(admin_client):
    response = admin_client.get("/ops/billing/users/user-123")
    assert response.status_code == 200
    assert response.json()["plan"] in {"starter", "professional", "enterprise"}


def test_non_admin_cannot_access_billing_support(client, auth_headers):
    response = client.get("/ops/billing/users/user-123", headers=auth_headers)
    assert response.status_code == 403
```

- [ ] **Step 2: Implement admin support endpoints**

Expose admin-gated endpoints for:

```python
GET /ops/billing/users/{user_id}
POST /ops/billing/users/{user_id}/plan
GET /ops/billing/usage/{user_id}
GET /ops/billing/events/{user_id}
```

The plan correction endpoint should write an audit event and update local state.

- [ ] **Step 3: Verify the tests**

Run:

```powershell
uv run --directory services/api pytest tests/security tests/usage -q
```

Expected:

- support lookup tests pass.

- [ ] **Step 4: Commit**

```bash
git add services/api/app/main.py services/api/app/ops/router.py services/api/tests/security services/api/tests/usage
git commit -m "feat: add billing support tools"
```

### Task 5: Build Customer Billing UI

**Files:**

- Modify: `apps/web/src/features/pricing/pricing-page.tsx`
- Modify: `apps/web/src/features/account/account-page.tsx`
- Modify: `apps/web/src/features/settings/provider-settings-page.tsx`
- Modify: `apps/web/src/lib/api.ts`
- Test: `apps/web/src/features/pricing/pricing-page.test.tsx`

- [ ] **Step 1: Write the failing UI tests**

Add checks that:

```tsx
expect(screen.getByText(/current plan/i)).toBeInTheDocument()
expect(screen.getByText(/billing status/i)).toBeInTheDocument()
expect(screen.getByRole("button", { name: /upgrade/i })).toBeEnabled()
```

- [ ] **Step 2: Run the tests and confirm failure**

Run:

```powershell
pnpm --filter @docpilot/web test -- --run src/features/pricing/pricing-page.test.tsx
```

Expected:

- the new billing state assertions fail until the UI is wired.

- [ ] **Step 3: Implement billing state surfaces**

Show:

```tsx
plan name
billing period status
quota consumed
upgrade / manage buttons
```

Use backend data only; do not infer billing truth in the browser.

- [ ] **Step 4: Verify the UI tests**

Run:

```powershell
pnpm --filter @docpilot/web test -- --run src/features/pricing/pricing-page.test.tsx
```

Expected:

- pricing/billing UI tests pass.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/features/pricing/pricing-page.tsx apps/web/src/features/account/account-page.tsx apps/web/src/features/settings/provider-settings-page.tsx apps/web/src/lib/api.ts apps/web/src/features/pricing/pricing-page.test.tsx
git commit -m "feat: add customer billing surfaces"
```

### Task 6: Update Docs and Release Gates

**Files:**

- Modify: `docs/ops/release-checklist.md`
- Modify: `docs/product/known-limitations.md`
- Modify: `docs/product/vps-to-commercial-launch-gap-list.md`
- Modify: `docs/development/configuration-and-secrets.md`

- [ ] **Step 1: Update the release gate text**

Add explicit commercial-launch checks:

```markdown
- Stripe checkout, webhook reconciliation, and billing UI validated
- monthly usage ledger visible and enforced
- admin support lookup and plan correction verified
- billing smoke passed on HTTPS public URLs
```

- [ ] **Step 2: Update limitations**

State clearly that:

```markdown
- public self-serve billing is not considered launch-ready until quota and webhook state are verified in production-like deployment
- support tools are admin-only
- enterprise SSO/MFA is deferred
```

- [ ] **Step 3: No test required**

Run:

```powershell
rg "Stripe|billing|quota|usage ledger|support" docs -n
```

Expected:

- docs mention the commercial launch gate consistently.

### Task 7: Final Verification Gate

**Files:**

- No new files unless failures require fixes.

- [ ] **Step 1: Run backend billing/usage tests**

Run:

```powershell
uv run --directory services/api pytest tests/usage tests/billing tests/providers tests/security -q
```

Expected:

- billing, quota, and support tests pass.

- [ ] **Step 2: Run broader backend smoke tests**

Run:

```powershell
uv run --directory services/api pytest tests/test_openapi_smoke.py tests/chat/test_chat.py tests/export/test_export_docx.py tests/export/test_pdf_export.py -q
```

Expected:

- smoke tests pass.

- [ ] **Step 3: Run frontend tests and build**

Run:

```powershell
pnpm --filter @docpilot/web test -- --run
pnpm --filter @docpilot/web build
```

Expected:

- frontend tests pass;
- build succeeds.

- [ ] **Step 4: Run production readiness and launch smoke**

Run:

```powershell
python scripts/production_readiness.py --target production
```

Then run the public billing smoke against the deployed environment.

Expected:

- production readiness passes;
- the commercial launch smoke can reach the billing and pricing paths.

## Handoff Notes for the Next Model

- Do not expose real payment secrets or webhook payloads.
- Subscription truth lives in the backend, not the browser.
- Keep the billing support endpoints admin-gated.
- Use idempotent webhook reconciliation.
- Do not add enterprise SSO/MFA in this plan.
- If a billing state or usage migration conflicts with an existing Alembic head, create a merge revision instead of deleting history.

## Completion Criteria

This plan is complete when:

- checkout and webhook reconciliation are production-ready;
- the backend tracks usage durably and enforces entitlements;
- the UI shows billing state clearly;
- admin support tools can inspect and correct billing state;
- docs and release gates reflect paid launch requirements;
- focused backend and frontend checks pass.
