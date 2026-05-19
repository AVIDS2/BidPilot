# Playwright E2E Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add browser-level smoke coverage for the DocPilot Vite frontend, including unauthenticated shell checks and an opt-in seeded demo workflow.

**Architecture:** Playwright lives in `apps/web` and starts the Vite dev server through `webServer`. Always-runnable tests cover unauthenticated login/signup behavior. Demo-data tests are tagged and skipped unless `E2E_DEMO=1`, so local and CI smoke checks remain stable without requiring API/database services.

**Tech Stack:** Playwright Test, TypeScript, React/Vite, pnpm workspace scripts.

---

## File Map

- Modify `apps/web/package.json` to add Playwright scripts and dev dependency.
- Create `apps/web/playwright.config.ts` for Vite webServer, Chromium project, traces/screenshots, and `apps/web/e2e` test directory.
- Create `apps/web/e2e/auth.spec.ts` for no-backend unauthenticated smoke tests.
- Create `apps/web/e2e/demo.spec.ts` for opt-in demo-user flow using seeded API data.
- Modify `apps/web/tsconfig.json` to include Playwright config and e2e TypeScript files in type checking.
- Update `pnpm-lock.yaml` by installing `@playwright/test` through pnpm.

## Tasks

### Task 1: Add Playwright dependency and scripts

**Files:**
- Modify: `apps/web/package.json`
- Modify: `pnpm-lock.yaml`

- [ ] Add scripts `test:e2e` and `test:e2e:ui`.
- [ ] Add dev dependency `@playwright/test`.
- [ ] Run `pnpm --filter @docpilot/web add -D @playwright/test` from repo root.

### Task 2: Add Playwright configuration

**Files:**
- Create: `apps/web/playwright.config.ts`

- [ ] Configure `testDir: "./e2e"`.
- [ ] Configure Vite web server command `pnpm dev --host 127.0.0.1 --port 5173`.
- [ ] Configure `baseURL` from `E2E_BASE_URL` or `http://127.0.0.1:5173`.
- [ ] Use Chromium as the default smoke project.
- [ ] Enable trace on first retry, screenshots only on failure, and list/html reporters.

### Task 3: Add unauthenticated smoke tests

**Files:**
- Create: `apps/web/e2e/auth.spec.ts`

- [ ] Assert `/` redirects unauthenticated users to `/login`.
- [ ] Assert login page shows email/password controls and no social auth actions.
- [ ] Assert signup page shows registration controls and no social auth actions.

### Task 4: Add opt-in demo workflow smoke test

**Files:**
- Create: `apps/web/e2e/demo.spec.ts`

- [ ] Skip unless `E2E_DEMO=1`.
- [ ] Login with `E2E_DEMO_EMAIL`/`E2E_DEMO_PASSWORD`, defaulting to `demo@docpilot.ai`/`demo1234`.
- [ ] Confirm project list renders.
- [ ] Open `Acme Corp RFP Response` when seeded data exists.
- [ ] Verify project detail breadcrumb and key tabs render.

### Task 5: Verification

**Commands:**
- `pnpm --filter @docpilot/web exec tsc --noEmit`
- `pnpm --filter @docpilot/web exec vitest run`
- `pnpm --filter @docpilot/web exec playwright test --project=chromium --grep-invert @demo`
- Optional full demo path when services are running and seeded: `E2E_DEMO=1 pnpm --filter @docpilot/web exec playwright test --project=chromium --grep @demo`

## Self-Review

- The plan maps to MVP docs by validating the local browser demo path without making backend availability mandatory for baseline checks.
- The unauthenticated smoke tests are always runnable.
- The demo smoke test is explicit and opt-in.
- No new framework or service is introduced beyond the documented Playwright verification preference.
