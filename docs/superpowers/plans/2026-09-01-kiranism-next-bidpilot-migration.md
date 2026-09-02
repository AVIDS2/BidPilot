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
| ixartz/SaaS-Boilerplate | Marketing section source (`CenteredMenu`, `CenteredHero`, `Section`, `FeatureCard`, `CTABanner`) adapted into the landing and pricing/docs routes | MIT; attribution retained in `apps/web/THIRD_PARTY_NOTICES.md`; no Clerk/Drizzle/next-intl runtime imported |
| Wasp Open SaaS landing source | Sticky `NavBar` behavior, responsive Sheet menu, Hero/feature/FAQ/Footer section ordering and product-example presentation adapted to the BidPilot landing | MIT; Wasp router/auth/backend and unrelated example assets are not imported |
| BidPilot historical ReactBits landing at `1577ebc` | Superseded historical attempt; removed from the active graph on 2026-09-02 after the landing was aligned directly to Open SaaS source structure | First-party historical code; the active page uses the Open SaaS structure and Kiranism components instead |
| Open SaaS research | Architecture comparison only | MIT source researched; Wasp runtime is not mixed into the FastAPI/Pi product |
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
  runs, deliverables, reviews, members, account, inbox, my-work, radar,
  administration, admin and provider settings.
- [x] Restore public `/pricing` and `/docs` routes used by the prior Vite route
  contract and command palette.
- [x] Separate ordinary user workflow pages from administrator organization,
  Webhook and Pi runtime summaries with both navigation filtering and a server
  permission boundary.
- [x] Replace the starter favicon and metadata with the current BidPilot brand.
- [x] Update the production Next image and compose port/BFF environment.
- [x] Run focused production-bundle browser checks for authenticated API-backed
  route shapes: 16 product routes, desktop/mobile navigation, Agent Pi event
  projection, completed tool detail interaction and thinking shimmer.
- [x] Run a real authenticated account flow with the direct local API and an
  isolated local SQLite workspace fixture.
- [x] Review the historical rich BidPilot marketing composition, then replace
  it in the active graph with the direct Open SaaS landing source structure.
- [x] Fix local HTTP session cookies and make the Next login BFF verify the
  issued token before returning success; verify a real local login reaches the
  dashboard.
- [x] Adapt Open SaaS's sticky landing navigation and mobile Sheet behavior,
  and connect the public page to the Kiranism semantic theme selector and the
  project's Tabler icon family.
- [x] Align public landing motion with the installed Base UI/shadcn system:
  state-led Tabler SVG motion, product-preview feedback, reduced-motion
  fallback and CSS Grid FAQ expansion; use the existing Supabase preset as the
  default theme.
- [ ] Run the full PostgreSQL/Redis/MinIO/Worker integration flow in an approved
  local or staging environment.
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
8. Agent input remains available after a stale route asset: the page composer is
   statically loaded and the error action performs a full browser reload.
9. Desktop sidebar uses Kiranism Sidebar primitives; mobile uses its Sheet and
   the header trigger remains reachable.
10. Data pages show real freshness and retain prior data while refetching; the
   radar poll and chart transition are driven by the server query state.
11. Agent, chat and public marketing surfaces inherit the active Kiranism
    semantic theme. Open SaaS layout behavior and BidPilot motion components
    must not replace or leak a fixed palette into the authenticated app shell.
12. The public landing page exposes product copy only, keeps its responsive
    navigation/FAQ/CTA interactions, and has no source-template implementation
    notes visible to users.
13. `pnpm --filter @docpilot/web exec tsc --noEmit` and production build pass.
14. shadcn CLI info and Playwright desktop/mobile checks pass without console
   errors other than expected API responses in an unauthenticated environment.

## Acceptance evidence

- `pnpm --filter @docpilot/web exec tsc --noEmit`: passed.
- `pnpm --filter @docpilot/web format:check`: passed.
- `pnpm --filter @docpilot/web build`: passed; Next generated 33 routes,
  including `/admin`, `/administration`, `/inbox`, `/my-work`, `/radar`,
  `/pricing`, `/docs`, `/settings` and `/icon.svg`.
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
- Direct local-process checks: FastAPI `/health` 200, Pi `/health` 200, local
  account login through Next BFF, 14 user routes, public `/pricing` and `/docs`,
  and member denial of `/administration` and `/admin/users` passed. The local
  browser used only `127.0.0.1` endpoints.
- Local UI acceptance displayed three seeded projects, real readiness bars, run
  status chart, and seeded radar trend/queue data without public API calls.
- Local Pi conversation acceptance: the exact free-text message `你好` reached
  the Pi path through the local BFF and finished with `succeeded / pi`; the
  SQLite event chain contained `run.started`, durable message deltas,
  `message.completed` and `run.completed`, with no keyword route or fabricated
  thinking state. The local inbox stop action returned HTTP 200 and changed the
  seeded approval run to `cancelled`/`已停止`.
- Agent layout acceptance: standard desktop screenshot showed the message-state
  composer fully inside the AppShell viewport; user route snapshots showed no
  horizontal clipping in the project/radar/work pages. The compact breakpoint
  is `1024px`, where the environment surface opens through the installed
  shadcn Sheet.
- Agent theme acceptance: browser screenshots and computed styles passed for
  both Vercel light and dark modes; the Agent composer and transcript use the
  active background/foreground/primary tokens, and 320px plus 1440px checks
  showed no horizontal overflow.
- Public landing acceptance: a cold local Chromium load on `127.0.0.1:3300`
  showed the directly ported Open SaaS landing component order: sticky
  navigation, Hero, product/example carousel, highlighted feature, bento
  features, role surfaces, FAQ and Footer. The page exposed a semantic `h1`,
  stable product content, no horizontal overflow at 1440px or 390px, and the
  shadcn FAQ and theme selector opened. Scrolling changed the header to its
  rounded floating state; Light Green and dark mode changed the semantic page
  background and primary color.
- Public landing motion acceptance: the default theme is `supabase`; browser
  computed styles confirmed the FAQ panel uses `display: grid` and a
  `grid-template-rows` transition, and the radar, status and Tabler SVG nodes
  resolve to their intended marketing keyframes. A 1440px full-page screenshot
  showed the product preview, animated example surfaces and no full-width
  section divider bands.
- Public landing grid/showcase acceptance: the official Open SaaS bento data
  contract is filled with nine real BidPilot capabilities; the desktop grid
  measured three filled rows with no dangling blank area. The example track
  moved continuously while in view, paused when hovered, and stayed clipped
  inside its content container with no document overflow at 1440px or 390px.
- Local auth acceptance: the existing `leho@bid.test` fixture logged in through
  the Next BFF over plain HTTP and reached `/dashboard`; the dashboard loaded
  the account, project count, task state and readiness chart. The previous
  `登录成功，但无法读取当前账户` path was absent after the fix.
- Local readiness limitation: `/health` and the Pi sidecar `/health` returned
  200. `/health/ready` remains unavailable in the Docker-free profile because
  Redis and MinIO are intentionally not running; it is not used as evidence of
  a full local integration pass.
- Fixed legacy workflow rows without `execution_run_id`: user cancellation now
  closes the durable runtime row when there is no worker execution to interrupt;
  new demo rows seed the execution bridge and the service regression is covered
  by `test_unlinked_workflow_cancellation_closes_legacy_runtime_row`.
- The local API test suite was not rerun because this worktree has no dedicated
  `DOCPILOT_TEST_DATABASE_URL` ending in `_test`, and approved local
  PostgreSQL/Redis/MinIO processes are intentionally absent. SQLite was used
  only for the direct local browser contract profile; no production database
  was used as a test database.

## Development log

### 2026-09-01

- Adopted Kiranism source in an isolated worktree.
- Added same-origin FastAPI BFF and cookie session boundary.
- Ported the real BidPilot API client and Agent state/timeline modules.
- Added Next App Router product screens and production image configuration.
