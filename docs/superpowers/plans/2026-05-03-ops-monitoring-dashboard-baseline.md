# Ops Monitoring Dashboard Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing Project Detail `System` tab runtime summary into a focused, testable monitoring baseline.

**Architecture:** Keep `/ops/runtime-summary` unchanged. Create a focused React component that accepts the existing `RuntimeSummary` type and renders the monitoring cards, then replace the inline System Status card markup in `ProjectDetailPage` with that component.

**Tech Stack:** React, TypeScript, Vite, Vitest, Testing Library, shadcn/ui Card/Badge/Progress/Skeleton.

---

### Task 1: Runtime Summary Component

**Files:**
- Modify: `apps/web/src/features/ops/runtime-summary.tsx`
- Create: `apps/web/src/features/ops/runtime-summary.test.tsx`
- Modify: `apps/web/src/features/projects/project-detail-page.tsx`

- [ ] **Step 1: Write the failing component tests**

Create `apps/web/src/features/ops/runtime-summary.test.tsx` with tests that render healthy, attention-needed, and loading states.

- [ ] **Step 2: Run the targeted test to verify RED**

Run: `pnpm --filter @docpilot/web exec vitest run src/features/ops/runtime-summary.test.tsx`

Expected: fail because `RuntimeSummaryCards` is not exported yet.

- [ ] **Step 3: Implement `RuntimeSummaryCards`**

Replace the placeholder `RuntimeSummary` component with an exported `RuntimeSummaryCards` component that accepts `summary?: RuntimeSummary` and renders the cards.

- [ ] **Step 4: Wire `ProjectDetailPage` to use the component**

Import `RuntimeSummaryCards` from `@/features/ops/runtime-summary` and replace the inline System Status card content in the `ops` tab.

- [ ] **Step 5: Run targeted frontend tests**

Run: `pnpm --filter @docpilot/web exec vitest run src/features/ops/runtime-summary.test.tsx`

Expected: tests pass.

- [ ] **Step 6: Run frontend type and unit verification**

Run:

```powershell
pnpm --filter @docpilot/web exec tsc --noEmit
pnpm --filter @docpilot/web exec vitest run
```

Expected: both pass.
