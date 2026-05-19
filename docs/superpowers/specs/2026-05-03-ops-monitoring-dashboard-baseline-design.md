# Ops Monitoring Dashboard Baseline Design

## Goal

Improve the existing Project Detail `System` tab so it has a focused, testable monitoring baseline without changing the backend API contract.

## Scope

This design covers one frontend-only increment:

- Extract runtime summary cards from `ProjectDetailPage` into a focused component.
- Render queue depth, failed runs, and draft success rate with clear status labels.
- Keep the existing `/ops/runtime-summary` payload unchanged: `queue_depth`, `failed_runs`, and `draft_success_rate`.
- Keep RBAC behavior unchanged: only admin users see the `System` tab and trigger the ops query.

This design does not add a new route, new backend fields, Prometheus metrics, or external dashboard tooling.

## Approach

Create `apps/web/src/features/ops/runtime-summary.tsx` as the single owner of the runtime summary display. `ProjectDetailPage` will pass the existing `ops` query data into that component. The component will also support a loading state when no summary has loaded yet.

The status model is derived locally:

- `Healthy` when failed runs are `0`, queue depth is below `10`, and draft success rate is at least `0.95`.
- `Attention needed` otherwise.

## Testing

Add `apps/web/src/features/ops/runtime-summary.test.tsx` with Vitest and Testing Library coverage for:

- healthy summary rendering;
- attention-needed rendering when failures or poor success rate exist;
- loading skeleton rendering when the summary is absent.

## Verification

Run:

```powershell
pnpm --filter @docpilot/web exec vitest run src/features/ops/runtime-summary.test.tsx
pnpm --filter @docpilot/web exec tsc --noEmit
pnpm --filter @docpilot/web exec vitest run
```
