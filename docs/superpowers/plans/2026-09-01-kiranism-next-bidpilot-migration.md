# Kiranism Next BidPilot Migration

## Status

- Branch: `codex/kiranism-bidpilot`
- Scope: BidPilot AI 招标响应平台前端
- Frontend base: `Kiranism/next-shadcn-dashboard-starter` source, MIT
- Backend boundary: existing FastAPI control plane + Pi sidecar + Worker
- Local Docker: forbidden by project owner; local web/API use direct processes
- VPS Docker: retained for the production topology only

## Product boundary

The migration replaces the old Vite route shell and keeps the existing business
runtime. It does not replace project truth, authentication policy, Pi event
contracts, tools, approvals, or the PostgreSQL model.

```text
Browser
  -> Next App Router UI (Kiranism Base UI/shadcn components)
  -> same-origin Route Handler BFF (HttpOnly cookie, REST/SSE forwarding)
  -> FastAPI control plane
       -> PostgreSQL / pgvector
       -> Worker / Celery / Redis
       -> Pi Agent sidecar through the signed bridge
```

## Source decisions

| Source | Use | License / boundary |
| --- | --- | --- |
| Kiranism dashboard starter | App Router, Base UI shadcn primitives, sidebar, forms, tables, themes, query setup | MIT; copied source remains in `apps/web` |
| Existing BidPilot frontend at `fd2cc21` | API types/client and Pi Agent timeline/state projection | First-party project code; adapted to Next routing and BFF |
| Open SaaS / ixartz research | Composition and landing-page references only | MIT sources researched; no runtime dependency |
| Supabase documentation | Future optional Auth/Storage adapter decision | No Supabase credentials or runtime dependency in this phase |

## Task checklist

- [x] Create an isolated branch from production commit `fd2cc21`.
- [x] Import the Kiranism source and verify its original typecheck/build.
- [x] Remove Clerk/Sentry runtime coupling from the active Next graph.
- [x] Add Next Route Handler auth/BFF with HttpOnly access and refresh cookies.
- [x] Adapt the typed BidPilot client to same-origin `/api/bidpilot/*`.
- [x] Move Agent route navigation from React Router to Next App Router.
- [x] Preserve Pi event-driven thinking, tool, approval, cancellation and replay state.
- [x] Add real-data pages for dashboard, projects, requirements, knowledge,
  runs, deliverables, reviews, members, account, admin and provider settings.
- [x] Replace the starter favicon and metadata with the current BidPilot brand.
- [x] Update the production Next image and compose port/BFF environment.
- [x] Run focused production-bundle browser checks for authenticated API-backed
  route shapes: 16 product routes, desktop/mobile navigation, Agent Pi event
  projection, completed tool detail interaction and thinking shimmer.
- [ ] Run a real authenticated account flow with the direct local API.
- [ ] Promote to VPS only after explicit release confirmation.

## Acceptance contract

1. Public `/` renders without contacting the backend when no auth cookie exists.
2. `/dashboard` and all product routes redirect unauthenticated users to sign-in.
3. Login/register errors are returned from FastAPI without exposing tokens to
   browser JavaScript or URL query strings.
4. Project, requirement, run, delivery and team pages distinguish loading,
   error and empty states; an unresolved query is never displayed as zero.
5. Agent `thinking` is shown only after the real Pi `thinking.started` event.
6. Tool cards remain in the transcript after success/failure and can be opened.
7. Stop calls the durable runtime cancel endpoint and keeps the terminal event.
8. Desktop sidebar uses Kiranism Sidebar primitives; mobile uses its Sheet and
   the header trigger remains reachable.
9. `pnpm --filter @docpilot/web exec tsc --noEmit` and production build pass.
10. shadcn CLI info and Playwright desktop/mobile checks pass without console
    errors other than expected API responses in an unauthenticated environment.

## Acceptance evidence

- `pnpm --filter @docpilot/web exec tsc --noEmit`: passed.
- `pnpm --filter @docpilot/web format:check`: passed.
- `pnpm --filter @docpilot/web build`: passed; Next generated 27 routes,
  including `/admin`, `/settings` and `/icon.svg`.
- `pnpm audit --prod`: no known vulnerabilities.
- shadcn CLI `info --json` from `apps/web`: Next 16, RSC, Tailwind v4,
  `base-nova`, Base UI and Tabler icons confirmed.
- Playwright CLI against the compiled production server: all 16 authenticated
  route fixtures loaded; desktop collapse/logo restore and mobile Sheet open,
  route selection and close passed with zero console errors.
- Playwright CLI Pi event fixture: `assistant.start`, turn lifecycle,
  `thinking.started/completed`, tool success, assistant message and terminal
  event rendered; completed tool detail remained mounted and opened via a real
  pointer click with zero console errors.
- Playwright CLI delayed stream fixture: the thinking indicator appeared only
  while the stream carried `thinking.started`; computed CSS contained the
  `assistant-thinking-shimmer` animation and gradient background.
- Direct public read-only checks: Web HTTP 200 and API readiness HTTP 200.
- The local API test suite was not rerun because this worktree has no dedicated
  `DOCPILOT_TEST_DATABASE_URL` ending in `_test`, and local Postgres/Redis/
  MinIO processes are intentionally absent. No production database was used
  as a test database.

## Development log

### 2026-09-01

- Adopted Kiranism source in an isolated worktree.
- Added same-origin FastAPI BFF and cookie session boundary.
- Ported the real BidPilot API client and Agent state/timeline modules.
- Added Next App Router product screens and production image configuration.
