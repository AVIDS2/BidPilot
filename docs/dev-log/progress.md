# Progress Log

## 2026-09-03 production delivery

- Promoted the final release commit `7843f42132cb179df18642351f47b25945408643`
  to the VPS at `/app/bidpilot/repo`. The production environment is now `pi`
  with the MiMo provider and `mimo-v2.5-pro`; the embedding provider remains
  OpenRouter.
- Updated the Pi dependency tree with fixed `fast-uri` and `qs` overrides;
  `pnpm audit --prod` reports no known vulnerabilities, and the final Pi/Web
  images were rebuilt from the updated lockfile.
- The release gate completed successfully: production Compose config,
  readiness, Alembic migration, LangGraph checkpoints, Pi sidecar health,
  API health, Worker, Worker Beat, and Web startup all passed.
- Created and verified the public test account through registration, email
  verification, and login. Public dashboard and Agent routes loaded with
  authenticated API calls returning 200.
- Public Agent acceptance passed with a real MiMo response, a native Pi
  read-only project tool call, and an immediate-stop run that ended as
  `cancelled` without leaving a running production run. The browser route
  smoke covered 18 user, admin, workflow, settings, and Agent routes; no
  page-level error or browser console error was observed.
- VPS Docker Build Cache was pruned from 11.54 GB to 0 B. Images, running
  containers, PostgreSQL, Redis, MinIO, and their volumes were preserved.
- Rollback material is retained in the timestamped production `.env` backup;
  the temporary release bundle was removed after the remote checkout.

## 2026-09-03 MiMo local provider acceptance

- Switched the local Pi Assistant profile to the Xiaomi MiMo OpenAI-compatible
  endpoint with model `mimo-v2.5-pro`; the embedding profile remains the
  existing OpenRouter model.
- Stored the MiMo credential in the Windows current-user environment as
  `MIMO_API_KEY`. The local API launcher reads it in memory and fails closed
  when it is absent; it never falls back to the old provider credential.
- The model resolver now gives the dedicated MiMo alias priority whenever the
  configured assistant profile is MiMo, so an old generic assistant variable
  cannot silently select a different provider.
- Sent a real browser prompt through the local BFF/SSE path. The response
  identified `MiMo-v2.5-pro`, and the persisted runtime row completed with
  `engine=pi` and `model=mimo-v2.5-pro`.
- No prompt, handler, keyword routing, or business-tool behavior was changed
  by this provider switch. Production configuration remains unchanged.

## 2026-09-02 assistant refresh, stream and replay convergence

- Reproduced the reported public failure against the running system. The VPS
  API had 15 PostgreSQL connections in `idle in transaction`, exhausting its
  default `5 + 10` QueuePool; long-lived SSE authentication dependencies were
  holding database sessions open. The code now authenticates streams through a
  short-lived session, and workflow polling also opens a short read session per
  interval.
- Browser session renewal now works when only the HttpOnly refresh cookie
  remains. Temporary API `429/5xx` responses no longer clear the authenticated
  identity, and the client no longer retries a `429` with a 1/2/4-second burst.
  Refresh tokens are sent to the backend in a JSON body on the new BFF path;
  the legacy query parameter remains accepted for compatibility.
- Runtime recovery now uses `live_only` for active monitoring and does not
  start a poller for stale queued workflow children. The explicit agent URL
  restore is guarded against the React state-change re-entry that previously
  requested the same chat history twice. The unused footer history control,
  which was covered by the composer, was removed; the top conversation menu is
  the single history entry point.
- Pi durable `message.delta/message.completed` events are replayed into the
  ordered public transcript without duplicating stored final text. Execution
  items receive their frontend execution group, and the legacy projection
  attaches ungrouped items at the first matching turn position. No prompt,
  Pi handler, tool schema, or keyword intent routing was changed.
- Local evidence: Next production build, TypeScript, Python compileall and
  Ruff pass; Agent/web targeted tests pass (`71 tests`). The Python integration
  suite still requires a configured dedicated `_test` database. Changes are
  local only; the unhealthy VPS has not been restarted or redeployed in this
  task.

## 2026-09-03 Pi Web parity and cancellation/replay closeout

- Checked the current official Pi repository and its RPC/SDK documentation,
  plus the MIT `agegr/pi-web` and `jmfederico/pi-web` source implementations.
  There is no official `pi-web` package inside Pi; those projects are browser
  wrappers around a persistent Pi session. BidPilot keeps the official
  `createAgentSession` sidecar and PostgreSQL control plane because Pi Web's
  trusted local-filesystem model is not a multi-tenant business backend.
- Found and fixed two remaining user-visible replay defects: historical
  `open_page` events no longer navigate the current browser, and successful
  skill bootstrap events are omitted from the product timeline so multiple
  Skills do not become duplicate preparation cards.
- Found a local cancellation race where the API and interrupted direct executor
  could both finalize the same run under SQLite. Runtime terminal transitions
  now use a conditional update, leaving exactly one message/terminal event pair;
  the new regression test and a real browser cancellation both pass.
- Real local evidence: stop control became clickable in 83 ms, cancellation
  returned 200, the UI showed one cancellation result and returned to Send;
  restoring the historical conversation stayed on `/agent`, made one live-only
  runtime snapshot request, and did not poll the stale child run.
- The first public immediate-stop probe exposed a race in the previous 500 ms
  browser fallback: it could abort before the durable run ID arrived and leave
  the Worker running. The fallback was removed; the UI now waits for the real
  run ID and the delayed-ID regression test passes.
- Verification: web 11 files/116 tests passed, Pi 18 tests passed, backend
  targeted runtime/auth/rate-limit/heartbeat suite 46 passed, build and
  compileall passed. Production remains unchanged because the VPS API was
  previously unhealthy and a release/restart requires explicit confirmation.

## 2026-09-02 production auth proxy correction

- Real public browser acceptance reproduced the reported login failure: the
  main host's `/api/*` OpenResty location rewrote requests directly to FastAPI,
  so login returned raw access/refresh tokens while `/api/auth/me` had no
  browser session and refresh received a missing query parameter.
- Removed that bypass from the reviewed public web-host configuration. The main
  host now sends `/api/*` to the Next BFF, while `bidpilot-api.rglens.com`
  remains the direct FastAPI host. The old proxy file was backed up and the new
  configuration passed OpenResty syntax validation inside the 1Panel container
  before a hot reload.
- Acceptance with the verified production account reached `/dashboard` and
  rendered account/project data. The BFF response contained `ok/user` and set
  both HttpOnly session cookies. A password-reset request with a non-existent
  test email returned the normal anti-enumeration success state. No secret or
  password was logged.

## 2026-09-02 product marketing copy pass

- Reworked the visible landing copy for the actual B2B bid-response audience:
  the Hero now leads with “让好机会，更快变成好方案”, uses a short outcome-led
  supporting line and a single primary action, followed by product proof,
  role-specific value and objection-oriented FAQ. Section copy now follows the
  product promise “从机会到交付”, with short labels instead of feature
  implementation explanations.
- Removed template names, framework references, implementation explanations and
  internal system language from user-visible content. The page speaks to a bid
  owner, solution writer and reviewer as customers, not to a developer reading
  the source.
- Fixed the landing navigation contract while editing copy: Product,
  workflow, team-fit and FAQ remain section links; pricing points to the real
  `/pricing` route; product/role cards point to their actual workbench routes.

## 2026-09-02 landing grid and showcase correction

- Audited the visible layout against the official Open SaaS `FeaturesGrid`
  source. The earlier sparse result was caused by supplying six items to a
  nine-item small/medium/large bento contract, with a large item first. The
  landing now supplies nine real BidPilot capabilities in the upstream size
  sequence, so the six-column desktop grid fills three rows without a dangling
  blank area.
- Kept the upstream carousel card structure and in-view lifecycle, but changed
  the user-visible behavior from timer-based snap-to-card scrolling to a
  continuous duplicated-track marquee. It pauses on hover, is clipped inside
  the content container, and honors reduced-motion preferences.
- Browser regression caught and fixed a scrollbar-width overflow caused by the
  upstream full-viewport positioning pattern. The marquee now stays inside the
  page content container: desktop measured `1430/1430` and mobile `380/380` for
  document client/scroll width.

## 2026-09-02 landing motion and theme alignment

- Rechecked the Open SaaS source against the official landing composition. The
  product proof remains an application UI preview and the example carousel,
  rather than a generated illustration or a developer-facing template banner.
- Added restrained, state-led motion to the existing Tabler SVG icons and
  product surfaces: live response status, document/review confirmation, and a
  radar sweep. All marketing motion has a reduced-motion fallback.
- Updated the installed Base UI Accordion composition to use a CSS Grid row
  transition driven by Base UI's `data-open`, `data-starting-style` and
  `data-ending-style` attributes, so FAQ expansion and collapse interpolate
  instead of snapping. Removed the non-template full-width section rules and
  kept the borders belonging to the upstream navigation, cards, FAQ items and
  footer structure.
- Selected the existing `supabase` theme as the default preset for BidPilot.
  It provides the clearest brand-compatible green action color and avoids the
  previous Vercel pure black-and-white first impression; no new color system
  was introduced.
- Browser evidence: the default theme resolves to `supabase`, the FAQ panel
  reports `display: grid`, `transition: grid-template-rows`, and a `0fr` to
  content-sized row transition; animated marketing nodes resolve to their
  named keyframes, and the public page has no horizontal overflow at 1440px.


## 2026-09-02 Open SaaS landing alignment

- Compared the current Open SaaS `NavBar`/landing source through the official
  repository and docs. The template is MIT and its landing page is a separate
  set of React components; its Wasp router, auth and backend are not suitable
  to import into the FastAPI/Pi product.
- Adapted the upstream sticky navigation behavior to the current Kiranism Base
  UI stack: the top bar becomes a rounded floating header after scroll, and the
  mobile menu uses the installed shadcn/Base UI `Sheet` with an accessible
  title, product links, auth links and theme selector.
- Replaced landing-page Lucide/star-style decoration with the repository's
  configured Tabler icon family and changed the page surfaces, borders, CTA,
  canvas accent and preview to Kiranism semantic theme tokens. Browser checks
  confirmed Vercel/Light Green and dark-mode changes are visible on the page.
- Superseded by the direct Open SaaS landing port and grid/showcase correction
  entries below: the historical ReactBits motion path is no longer active.
  The current page uses the Open SaaS structure, the installed Kiranism
  components and a live BidPilot product preview.

## 2026-09-02 marketing and auth correction

- The public landing page was compared against the historical `1577ebc`
  implementation. The sparse SaaS composition was replaced by the actual
  previously reviewed ReactBits components: `CinematicHero`, canvas
  particles/grid, `BlurText`, `AnimatedContent`, `GlareHover`, `StarBorder`
  and `CountUp`, adapted to the current Next/Kiranism routes.
- The new page was cold-loaded through the real local `3300` server at desktop
  and 390px mobile sizes. It rendered the product preview, workflow,
  capability, plan, FAQ and CTA sections, with stable integer metrics and no
  horizontal overflow.
- Fixed the authentication race and local HTTP cookie mismatch. The login BFF
  verifies the issued access token against `/auth/me` before returning success,
  returns the verified user to the client, and derives `Secure` from the
  request/forwarded protocol instead of `NODE_ENV` alone. A real local fixture
  login reached `/dashboard` successfully.
- Web verification: `114` tests passed, TypeScript passed, and Next production
  build passed. The Docker-free local `/health/ready` probe remains outside the
  full integration gate because Redis and MinIO are intentionally absent.
- The production dependency audit initially exposed two `browserslist` high
  advisories in the Next/Babel chain. The workspace override now pins the
  patched `4.28.7` line; lockfile install and `pnpm audit --prod` are clean.

## 2026-09-02 direct Open SaaS landing port

- The prior custom `RichBidPilotLanding` was removed from the active route,
  together with its ReactBits/GSAP-only components and dependency. The public
  route now renders `open-saas/OpenSaasLanding.tsx`.
- The active page follows the official Open SaaS landing component order and
  source patterns: sticky `NavBar`, Hero, `ExamplesCarousel`, highlighted
  feature, bento `FeaturesGrid`, role surfaces, FAQ and Footer. Only Wasp
  router/auth/backend bindings were replaced with Next links, the existing
  FastAPI BFF routes and the installed Kiranism shadcn/Base UI components.
- Real Chromium checks passed for the desktop sticky/floating header, rotating
  example cards, 390px mobile Sheet, theme selector and dark-mode surface
  changes. The page has no horizontal overflow and no console errors in the
  clean browser session.

## 2026-09-02 Pi stream latency correction

- Root cause: the local direct-process facade discarded every event yielded by
  the queued Pi executor and replayed the durable timeline only after the
  executor finished. This produced a long blank interval followed by a burst
  of small deltas; it was an API transport bug, not a Pi chunk-size setting.
- Fixed the local facade with an in-memory event queue and an explicit event
  sink on `execute_queued_assistant_run`. The worker and local profiles still
  use the same Pi executor and native Pi event stream.
- Local probes after the fix: first SSE frame around `0.17s`, first visible
  assistant delta around `2.20s` through Next -> FastAPI, and native delta
  sizes remained small. No character splitting or keyword intent routing was
  added.
- The active local provider profile remains DeepSeek in the ignored source
  environment. MiMo-specific latency is intentionally unverified until the
  MiMo server-side key/profile is configured.
- Focused API runtime contract: `11 passed`; Ruff and Python compilation pass.

## 2026-09-02 release-candidate verification

- Restored the existing Web test suite after the Next migration had removed
  its Vitest dependencies and setup. The current Next App Router tests no
  longer depend on the old `react-router-dom` harness.
- Fixed history-menu event bubbling so Rename/Delete actions do not select and
  close the conversation row underneath them.
- Verification: Web `114 passed`, Worker `203 passed`, Pi `18 passed`, API
  static checks, Web typecheck and Next production build passed. API full
  local tests reached `841 passed / 62 skipped`; 11 storage/queue integration
  cases remain unavailable on the Docker-free machine because MinIO is not
  running. Production VPS readiness and public Web/API health both passed.
- The production server profile is already MiMo with the unchanged OpenRouter
  embedding model. Local startup now prefers MiMo when a server-only
  `MIMO_API_KEY` or `XIAOMI_API_KEY` alias exists; the current local source
  environment still has only the legacy DeepSeek profile, so no provider key
  was copied or repurposed.

## 2026-09-01 Kiranism migration acceptance

- Used the Kiranism dynamic primitives in user-facing product flows: shared
  `LiveSyncStatus` now exposes real query freshness and manual refresh; project,
  requirements, knowledge, delivery, review, run, dashboard and work views
  retain prior data while polling their relevant API state. Radar polls every
  30 seconds, shows source sync timestamps, pulses only for configured active
  sources, and animates the real Recharts trend when data enters or changes.
- Browser acceptance verified the radar timestamp changed across a real 30-second
  poll interval, the manual refresh called the local API, and the UI showed
  `95%` rather than the previous erroneous `9500%` match score. Project detail
  now uses the official Progress primitive for live readiness.
- Completed a user-side theme audit against the Kiranism Vercel/shadcn token
  system. The legacy Agent workspace, Claude transcript, activity timeline and
  native thinking indicator no longer reset the global palette or force light
  mode; both light and dark screenshots now keep the composer, timeline,
  history, preview and work overview on the active theme.
- Reused the SaaS Boilerplate marketing composition for the public landing page
  while removing source-template implementation copy and the old indigo/purple
  gradients. Section titles now use semantic heading levels, CTA/cards use
  theme tokens, and the public mobile menu and FAQ were browser-checked.
- A real local `你好` turn initially exposed a local-only API/Pi bridge secret
  mismatch (`401` from the Pi sidecar). The ignored local startup profiles now
  load the same secret source for both processes; the follow-up turn completed
  as `succeeded / pi` with durable message deltas and a terminal event.

- Hardened the Agent page for real AppShell constraints: the composer is now a
  stable static import, so a stale manifest cannot fail the whole page through
  a missing assistant chunk; the error-boundary action performs a full browser
  reload for stale route assets.
- Made the Agent surface responsive at the `1024px` compact boundary. The
  environment panel moves to the installed shadcn Sheet, embedded height is
  constrained to the space below the AppShell header, and example-card text
  overrides the Button `nowrap` default so long Chinese copy wraps instead of
  clipping.
- Rebuilt and browser-checked the local production server after these changes:
  the Agent composer and real Pi conversation rendered with zero console errors.

- Finalized the isolated `codex/kiranism-bidpilot` worktree with the direct
  Kiranism Next/shadcn Base UI source and the existing FastAPI/Pi business
  boundary.
- Fixed a real Agent timeline hit-area bug: the closed child detail grid used
  `0fr` but still occupied layout space, allowing the parent task button to
  intercept clicks. `minmax(0, 0fr)` now removes the closed child hit area;
  completed tool details remain available after terminal events.
- Removed remaining Base UI `nativeButton={false}` link compositions from
  deliverables, GitHub CTA and pagination, following the current shadcn Base UI
  link guidance (`buttonVariants` plus a semantic anchor/link).
- Added valid `/admin` and `/settings` index routes so Kiranism breadcrumb
  prefetches no longer produce 404 console errors.
- Compiled production browser acceptance passed for the authenticated product
  routes, desktop/mobile navigation, Agent event projection, tool detail
  interaction, and delayed native thinking shimmer. `tsc`, format check,
  production build and `pnpm audit --prod` passed; lint exits 0 with advisory
  upstream/source warnings.
- The direct local profile is now running and verified: Next `3300` -> FastAPI
  `8000` -> Pi `8787`, with isolated SQLite demo data and no local Docker,
  public API, Redis, MinIO or Worker. A real `你好` turn completed as Pi with
  durable `run.started`/message/`run.completed` events. The local inbox stop
  action also completed a previously unlinked workflow row with HTTP 200.
- Full PostgreSQL/Redis/MinIO/Worker parity remains a separate environment gate;
  production promotion is still a separate release decision.

## 2026-09-01 Kiranism Next frontend base

- Created isolated branch `codex/kiranism-bidpilot` from production commit
  `fd2cc21` and imported the MIT Kiranism dashboard source directly.
- Replaced the active Vite route shell with Next.js 16 App Router routes while
  retaining FastAPI/Pi/Worker/PostgreSQL as the business runtime.
- Added same-origin Route Handler BFF endpoints with HttpOnly auth cookies,
  REST forwarding, multipart forwarding and streaming response preservation.
- Ported the real BidPilot API client and Pi event-driven Agent state/timeline;
  there is no keyword intent classifier, scripted model transport or fake
  thinking state in the new route graph.
- Added real-data project, requirement, knowledge, run, delivery, review,
  member, account, admin and provider screens with Kiranism Base UI primitives.
- Replaced the tab icon using Next `app/icon.svg`, removed Clerk/Sentry runtime
  coupling, and updated the VPS Next image/compose port and BFF environment.

## 2026-08-31 workbench branding and responsive navigation

- Replaced the stale browser favicon with the current BidPilot Logo and added
  a versioned favicon URL to invalidate old tab-icon caches.
- Made long workspace names shrink and ellipsize inside the header controls.
  Desktop sidebar collapse now keeps only the existing collapse button; in the
  collapsed state the Logo is the sole expand action.
- Added a shadcn `Sheet` navigation drawer and topbar trigger for mobile. The
  desktop and mobile menus share the same route model, and mobile navigation
  closes after a route is selected.
- Added Playwright coverage for desktop collapse/Logo restore and Pixel 7
  mobile open/close behavior. Full Web E2E passed `40` tests with `24` opt-in
  backend/demo scenarios skipped.

## 2026-08-31 runtime lifecycle, Pi alignment and acceptance hardening

- Removed the public Pi adapter's implicit `maxTurns=24` stop policy. The
  official `AgentSession` now keeps its native continuation behavior; an
  explicit caller may still opt into `maxTurns` for a deliberate bounded run.
- Added Worker Beat reconciliation for expired approvals and active runtime
  rows that have no live transactional-outbox delivery. Stale assistant turns
  are closed as durable failures, while live leases and recent missing-input
  pauses remain protected. The user-facing Work Overview requests only
  background-run kinds and renders loading/error states instead of stale
  assistant rows or false empty states.
- Kept completed tool details mounted after Pi emits terminal lifecycle events,
  normalized API 404/422 errors with `code`, `message`, `details` and
  `request_id`, and corrected the release readiness fixture from `harness` to
  `pi`. The active administration detail pages now use shadcn/Base UI
  Button/Input/Select/Field/AlertDialog primitives.
- Fixed the dashboard's project error path so an unresolved project query does
  not become a fake zero-project onboarding state. Added Pi sidecar tests and
  build to CI/release gates.
- Updated the workspace lock with patched dependency resolutions. Verified the
  actual installed graph with `pnpm audit --prod`: `high=0`, `critical=0`.
- Pinned the repository, CI and Node image installs to `pnpm@11.19.0` so the
  workspace override configuration and frozen lockfile are checked by the same
  toolchain. Final local acceptance: Web `198` tests passed, Pi `18` tests and
  build passed, Worker `203` tests passed, Ruff passed, and Playwright passed
  `40` desktop/mobile tests with `24` opt-in backend/demo tests skipped. The
  full API suite reached `836 passed / 62 skipped`; its `9` failures are the
  pre-existing MinIO integration cases blocked by the unavailable local
  `localhost:9000` service.

## 2026-08-31 Pi full-access false failure fix

- Reproduced the reported `full_access` failure from the production runtime
  record. Pi completed the model/tool loop and all observed business tools
  succeeded, but the final answer exceeded an accidental `2000`-character
  Pydantic limit on `RuntimeEventDraft.public_summary`.
- Removed that artificial response cap from the API event draft and shared
  runtime contract. Full assistant replies remain intact in chat messages,
  runtime results, and completed-message event payloads; no Pi/Harness prompt,
  turn, or reply truncation was added.
- Verification: API runtime/contract/event suites `36 passed`, API Ruff and
  compile checks passed, and the dedicated long `full_access` regression now
  finishes as `succeeded` with the exact full response preserved.

## 2026-08-30 MiMo direct-balance provider switch

- Confirmed the production environment was still resolving the old DeepSeek
  configuration, not OpenCode Go. Switched the documented platform profile to
  Xiaomi MiMo direct balance at `https://api.xiaomimimo.com/v1` with model
  `mimo-v2.5-pro`; the API keeps the product profile `mimo` and the Pi sidecar
  uses Pi's built-in `xiaomi` provider.
- Kept MiMo credentials server-side. Assistant, Worker fallback adapters, and
  legacy title generation resolve the same profile; no key is included in the
  repository or browser bundle. No local Docker or sub-agent process is used.
- Verification before production promotion: API provider/runtime/chat target
  `69 passed`, Worker adapter target `37 passed`, Pi `17 passed`, Web account
  `4 passed`, Python compile, TypeScript check, and provider contract checks
  passed. MiMo direct-balance probe returned HTTP 200. The first VPS build
  attempt was stopped by a concurrent Web Vite `SIGSEGV` under the host's
  memory pressure; old containers stayed up, and the deploy script now builds
  application images sequentially with restore-on-failure behavior.
- Production promotion completed at commit `6128f63` using the sequential VPS
  Compose path. API, Pi, Web, Worker, PostgreSQL, Redis, and MinIO containers
  are running; migration, readiness, and checkpoint one-shot services exited
  successfully. The public API `/health` and `/health/ready` endpoints returned
  HTTP 200 with all dependency checks ready, and the public Web/login routes
  loaded without browser console errors.
- The production environment is configured for MiMo direct balance through the
  official OpenAI-compatible endpoint and Pi's built-in `xiaomi` provider
  mapping. A real low-token MiMo request returned HTTP 200. Full authenticated
  conversation acceptance was not fabricated because no production login
  credentials were available in the browser session.
- Audited the public `/docs` route after promotion. Replaced stale developer
  setup instructions, placeholder provider credentials, and obsolete health
  endpoints with the real user workflow, server-side MiMo/Pi boundary, and
  platform safeguards. Fixed `AnimatedContent` so animation-only props do not
  leak into DOM attributes; local browser reload now reports zero console
  errors at desktop and 390px mobile widths.
- Post-fix verification: Web `40` test files / `195` tests passed, production
  Vite build passed, public release smoke from the VPS returned `30/30` with
  zero failures and p95 `543.70ms`, and the native Pi/MiMo smoke emitted the
  complete thinking and agent settlement lifecycle without a failure event.

## 2026-08-29 account settings shadcn alignment

- Rebuilt the active `/account` route around the installed shadcn/base-nova
  primitives: line tabs and tab panels, cards, fields, avatar and badges,
  switches, progress, skeletons, and empty states. Replaced the page's bespoke
  action and form markup without changing its existing account APIs.
- Kept notification preferences in the user-scoped TanStack Query cache after
  a mutation so a successful switch does not immediately revert to stale data.
  The real QA account was toggled and restored through the browser.
- Verified profile, notification, security, and organization tabs at desktop
  and 390px mobile widths; the mobile settings navigation remains intentionally
  horizontally scrollable and the document has no horizontal overflow.
- Verification: focused account tests `4 passed`, Web full suite `194 passed`,
  production build passed, and lint passed with zero errors and five existing
  hook-dependency warnings. No public deployment was performed.

## 2026-08-29 Pi runtime and browser acceptance pass

- Completed the Pi runtime correction across the sidecar, API bridge, Worker,
  and web projection. New assistant turns continue through Pi's official
  `AgentSession` path; no message keyword classifier or automatic legacy
  fallback was added. Native `thinking.started/completed`, tool lifecycle,
  `agent_settled`, approval, missing-input, retry, and failure states are
  projected from structured runtime events.
- Kept durable tool rows visible after a terminal event, replayed the complete
  PostgreSQL run after a Redis terminal frame, correlated duplicate live/durable
  projections, scoped stale watchers by conversation and generation, and
  associated session errors with their own runtime run.
- Fixed active cancellation at the transport boundary. The API records the
  durable request, Pi receives the official abort signal, the affected sidecar
  response is closed, and the API interrupts its same-process Worker waiter
  before committing `run.cancelled`. A clean v8 stack was tested with a real QA
  account: an immediate stop click restored the composer in under two seconds,
  the page showed `已取消这次操作`, the database run was `cancelled`, and the
  work overview returned to `目前没有后台工作`.
- Real browser checks also covered a plain `你好` response with no tool call,
  native thinking lifecycle frames with the animated `assistant-thinking-shimmer`
  label, a read-only `search_projects` call whose tool card survived reload,
  and production-preview navigation/hard reload across the workbench routes
  at desktop and mobile widths without a dynamic-import boundary or horizontal
  overflow.
- Converted the active Agent thread controls to the existing shadcn `Button`,
  `Input`, `Textarea`, and `DropdownMenu` primitives, and removed the purple
  focus halo from the composer. The legacy floating panel remains a separate
  compatibility surface documented for a later focused audit.
- Verification: API focused cancellation/runtime suites `26 passed`, Worker
  `197 passed`, Pi `17 passed`, Web `190 passed` plus the projection-focused
  regression suite `67 passed`; Web lint has no errors and retains five existing
  hook-dependency warnings; Pi TypeScript/build, Web production build,
  `git diff --check`, and local readiness checks passed. Docker image rebuild
  was not used because Docker Hub anonymous token retrieval was unavailable;
  the runtime/browser acceptance used isolated local API, Worker, Pi, Redis,
  PostgreSQL, and Vite processes instead.

## 2026-08-28 Pi cancellation and stale-release recovery

- Traced the reported long-running `你好` failure to a whitespace-only Pi
  `text.delta` being rejected by the public runtime event schema. Formatting-only
  chunks are now buffered into the next visible delta without losing word
  spacing or allowing an empty public summary.
- Wired the user stop control to the durable runtime cancel endpoint and Pi's
  official `AgentSession.abort()`. Queued runs are rechecked before startup;
  running runs receive a sidecar abort; the browser stays in `正在停止` until a
  durable terminal event is observed.
- Added the same internal sidecar authentication to subagent requests, and
  added release-cache recovery for Vite dynamic imports: HTML is no-store,
  hashed assets remain immutable, and one stale-chunk reload is attempted.
- Verification: Web full suite `184 passed`, Agent stop/runtime focused tests,
  TypeScript and ESLint, Pi sidecar `17 passed` plus production build, API
  runtime tests `25 passed`, Worker subagent tests `2 passed`, API full suite
  `839 passed / 60 skipped`, and API/Worker Ruff/Python checks passed.

## 2026-08-28 Pi terminal boundary and composer regression fix

- Fixed the production Pi integration to consume the official
  `AgentSessionEvent` `agent_settled` event and await its asynchronous delivery.
  `agent_end` is only one low-level attempt and may be followed by retry,
  compaction or queued continuation.
- Confirmed from the deployed runtime records that the affected `你好` and
  `逆天` turns made no tool calls; the failure was in terminal-event projection,
  not keyword intent routing. The public path remains Pi-only and does not
  inspect user wording to select tools.
- Removed the composer `ring-2` focus halo. Focus now uses a restrained border
  color change without the oversized purple outline shown on mobile.
- Added Pi regression coverage for a plain conversational response and the
  official terminal event boundary. Updated the runtime architecture note to
  keep this contract explicit.

## 2026-08-28 workbench navigation and UI consistency pass

- Added shared route loaders and intent-based prefetching for authenticated
  workbench navigation. Nested route Suspense now preserves the shell and
  renders shadcn Skeleton structure during chunk loading.
- Added bounded query defaults (`30s` stale window, `5m` cache lifetime, one
  retry, and no focus-triggered refetch) and removed transient zero/empty
  presentation from dashboard, inbox, my work, runs, knowledge, projects,
  radar, deliverables, reviews, and project-detail loading states.
- Converted the active Agent Composer menus to shadcn `DropdownMenu` and
  `DropdownMenuRadioItem`, and converted its common history, preview, and
  composer controls to `Button`, `Input`, and `Textarea`. The legacy floating
  panel still has a separate hand-built menu path and remains an explicit
  follow-up audit item.
- Replaced project-detail inspector loading markup with shadcn `Skeleton` and
  added browser coverage proving delayed project data does not render a false
  empty state or zero tab count.
- The Agent entry chunk is now about `55 KB` minified; the build still reports
  a separate roughly `512 KB` Markdown/rendering dependency chunk. Further
  lazy loading of rich-message rendering is intentionally left as a focused
  follow-up so the active transcript behavior is not destabilized.
- Verification: TypeScript, Agent/workbench focused tests, production Vite
  build, and Chromium/Pixel 7 UI flows passed. API PostgreSQL tests remain
  gated by the unavailable Docker engine and dedicated `_test` database.

## 2026-08-27 Pi failure and live thinking projection fix

- Persisted `RuntimeAction.tool_call_id` and carried it through capability
  events so the immediate Pi `tool.started` frame and durable success/failure
  replay update one execution item instead of rendering duplicate rows.
- Removed the synthetic `本轮已结束（工具未收到完成事件）` fallback. An
  interrupted browser stream now drops only unconfirmed transient tool cards;
  real durable capability failures remain visible with their actual public
  failure state.
- Separated `isThinking` from transport `isStreaming`. The UI shows the live
  thinking indicator only after Pi emits `turn.started` or
  `thinking.started`, and clears it on native completion, text, tool, or
  terminal events.
- Terminal assistant failures are projected as a dedicated session error;
  failure messages are not replayed as ordinary assistant answers, while any
  already-streamed public text remains separate and recoverable.
- Added regression coverage for duplicate tool correlation, ghost-tool
  suppression, terminal failure replay, and native thinking boundaries.
- Verification: Web `38` test files / `175` tests, Agent workspace Playwright
  `8/8` on desktop and mobile Chromium, TypeScript/Vite build, Pi sidecar
  tests/build, API/Worker Ruff and Python compile checks passed. Full API
  PostgreSQL tests were not run because Docker and the required dedicated
  `_test` database were unavailable locally.

## 2026-08-25 user-facing Agent workspace context

- Reworked the right-side Agent context panel from a developer-facing runtime
  diagnostic into a user-facing **工作概览**. It now reads live project and run
  APIs and shows only current project, active background work, recent work, and
  actionable links. Pi/MCP/sandbox/provider counts and internal engine details
  are no longer exposed in the conversation surface.
- Reorganized the conversation switcher by durable `project_id`: each project
  is a work partition containing its conversations, while unscoped chats live
  under `个人会话`. Project headers open the project workspace directly.
- Added desktop and mobile regression coverage. Web full suite: 168 tests;
  Agent Playwright acceptance: 8/8 across Chromium and mobile Chromium;
  TypeScript and Vite production build passed.

## 2026-08-25 chat history actions and scroll behavior

- Replaced the conversation row's raw CRUD icon buttons with the existing
  shadcn/base `DropdownMenu` and `Button` primitives. Pin, rename and delete
  remain available without keeping three low-signal controls visible in every
  row; deletion is a destructive menu action.
- Changed the Claude-style thread from unconditional smooth scrolling to a
  bottom-following policy: initial history restore jumps directly to the latest
  message, streaming follows only while the reader is near the bottom, and
  upward reading is preserved. A shadcn outline button appears only when the
  reader has left the bottom.
- Verification: Web full suite `168 passed`, Agent Playwright `8/8` on desktop
  and mobile Chromium, TypeScript and Vite build passed.

## 2026-08-24 live Pi runtime release

- Replaced the browser-first assistant projection with a run-scoped Redis live
  channel. The API subscribes before dispatching the Celery outbox task; the
  Worker-owned Pi session publishes the same user-safe runtime frames while it
  executes. PostgreSQL `RuntimeEvent` remains the durable source of truth for
  reconnect, refresh, and missed-event recovery. Closing the browser does not
  cancel the run.
- Fixed optimistic/durable message reconciliation by binding the optimistic
  assistant to `runtime_run_id` and merging by durable identity, runtime run,
  or message ID. This prevents a single user turn from rendering twice after
  history restoration.
- Removed the legacy CSS-injected `任务执行` heading. Runtime state is now
  projected from Pi lifecycle events and durable event metadata; no assistant
  message or tool-name substring selects a product mode.
- Added a paged, parent/child execution viewer for real `spawn_subagents`
  runtime runs and a specialized collapsible deep-research process surface.
  Presentation metadata is carried by runtime events, while ordinary tool
  calls retain the normal chronological projection.
- Verification: Pi sidecar real-model smoke passed with native
  `agent.started`, `turn.started`, `text.delta`, `turn.completed`, and
  `agent.completed`; Pi package tests `13 passed`; live Redis projection test
  `1 passed`; public Agent-workspace Playwright acceptance `4 passed` on
  Chromium; production readiness reports PostgreSQL, Redis, MinIO, Pi bridge,
  and Pi sidecar healthy; production Mem0 smoke passed capture, recall, and
  isolated cleanup.

- Extended the live projection to Pi-native tool starts. Skill loads now emit
  durable `capability.started/succeeded/failed` events with structured
  `resource_kind=skill` metadata; configured MCP tools are discovered as
  server-owned Pi tools and carry `resource_kind=mcp`, `resource_name`, and
  provider metadata. The browser merges the immediate Pi start frame with the
  later durable result by `tool_call_id`, so a slow Tavily/Context7-style call
  is visible before its response and never creates a duplicate row.
- Added structured activity labels for named Skills and MCP providers,
  preserving the existing parent timeline and parallel grouping. No user text
  or tool-name substring selects a runtime mode.
- Focused verification after this change: Pi `13 passed`, Web `166 passed`,
  API Skill/MCP/live projection tests `12 passed`; TypeScript, Ruff and
  compile checks passed.

## 2026-08-22

- Final acceptance pass for the memory/runtime release: API PostgreSQL suite
  `828 passed / 60 skipped`, Web `36 files / 163 tests` (single worker), Pi
  sidecar `13 passed`, Worker/LangGraph memory and subagent checks `11 passed`,
  TypeScript/Vite build and Ruff checks passed. A real OpenCode Go -> Pi
  sidecar smoke returned native `text.delta`, `turn.completed`, and
  `agent.completed` events without a tool call.
- Deployed the release to `bidpilot.rglens.com` at commit `0973ff3`; public API
  and Web returned HTTP 200 and all readiness checks (PostgreSQL, Redis,
  MinIO, Pi bridge, Pi agent) were healthy. Mem0 remains intentionally
  disabled because the VPS secret store has no Mem0 key; the image now
  includes `scripts/mem0_smoke.py` so the real cloud smoke can be run after
  secure injection.

- Added the official `mem0ai==2.0.18` adapter for optional long-term user
  profile memory. The adapter uses Context7-verified `MemoryClient` APIs,
  organization-scoped filters, bounded timeout/fail-open recall, asynchronous
  Worker capture, local idempotency ledger, and scoped account deletion. It is
  disabled by default until the deployment injects `DOCPILOT_MEM0_API_KEY`.
  The adapter now follows the official OR semantics for user/agent entity
  reads, deletes the two scopes separately, and omits Platform-only `app_id`
  when configured for a compatible OSS endpoint. Added the isolated
  `scripts/mem0_smoke.py` for a redacted real-cloud verification after secret
  injection.
  BidPilot `MemoryRecord` remains the evidence-backed business memory source;
  Pi `SessionManager.inMemory()` remains per-attempt working memory.
  The implementation was deployed in `04cf11e`; production health remained
  ready and the Worker registered `worker.capture_mem0_profile`. Mem0 remains
  disabled in production until its API key is injected through the deployment
  secret store; no key is stored in this repository.

- Fixed conversation isolation in the web Agent projection. The selected
  conversation is tab-scoped, active run/cancel targets are keyed by
  conversation ID, and stale watcher events cannot update the newly selected
  conversation. This prevents multiple open conversations from sharing one
  pause/cancel button or cancelling the wrong durable run. Focused Agent UI
  regressions passed after the change.

- Fixed the browser-owned Assistant execution gap exposed by public testing.
  New Pi assistant turns now persist a `worker.run_assistant_turn` outbox task
  and execute through Celery/Redis plus a signed API internal endpoint. The
  initial SSE is only a queued projection; closing the browser no longer
  cancels the model loop. Web history restore and the live watcher replay
  PostgreSQL runtime events by sequence cursor and merge the terminal chat row.
- Official Pi SDK review confirmed that `SessionManager` persistence is a
  local session-store API, not a distributed cloud queue. We kept Pi unchanged
  and use PostgreSQL RuntimeRun/RuntimeEvent + the existing Celery outbox for
  cloud durability.

- Completed the repository ownership baseline for clean development. The
  canonical interactive path is `apps/web` -> FastAPI control plane
  (`services/api`) -> signed `services/pi-agent` sidecar -> API capability
  bridge. Long-running ingestion, drafting, review and export remain in
  `services/worker` with LangGraph as an execution detail.
- Updated the root README, documentation map, repository blueprint, service
  boundaries, backend/frontend architecture references, engineering standards,
  capability matrix, runtime ownership README, and interview demo script so
  they describe the same boundaries.
- Explicitly quarantined the old Python Harness/ReAct/operator modules as
  historical replay compatibility. They are not a public entry point,
  production fallback, or destination for new features. No `temple/` reference
  material or user data was removed.
# 2026-08-25 generic deep research runtime

- Added the model-selected `start_deep_research` capability and a durable
  `RuntimeRun(kind=deep_research)` child. The Worker now performs a bounded
  planner -> parallel retrieval -> page/PDF reading -> source-backed claim
  verification -> report synthesis pipeline. The parent Pi turn receives a
  linked run and can continue without keeping the browser open.
- Added the generic `docs/agent-skills/deep-research/SKILL.md` contract. The
  existing tender skill is now a domain wrapper; it no longer describes a
  second search loop. The runtime remains bounded by depth-specific query and
  source budgets and stores a redacted report, sources and claims.
- Added Hikari Tavily gateway handling: custom gateways use Bearer auth and an
  automatically normalized `/search` endpoint; the official endpoint keeps
  its API key in the request body. Added unit coverage for both wire formats.
- Replaced the old flat deep-research web search rows with one live research
  surface showing phase, source/claim counts, evidence links, claim checks
  and the persisted report. Durable child events are polled only while the
  run is active and replayed after reconnect; no UI state is inferred from
  user text or search count.
- Verification: API/Worker Ruff and compile checks passed; Web TypeScript
  check passed; focused Web runtime/timeline tests passed (`28` tests). Full
  API pytest remains gated by the repository's dedicated PostgreSQL `_test`
  database safety guard; no production database was used as a substitute.

# 2026-08-25 Pi capability inventory

- Audited the Pi contract from API registry/catalog, Skills loader, MCP client,
  Pi sidecar sandbox/extensions, and the production container environment.
- Added `docs/architecture/pi-capability-inventory.md` with the code-supported,
  configured, and publicly deployed states kept separate. The audit confirms:
  local `42` business capabilities plus `read_skill`, five local Skills, no
  production MCP servers, Pi enabled, Mem0 enabled, and official Tavily active
  in production because Hikari base variables are not configured there.
- The next research passes are intentionally ordered by search/DR, Skills,
  MCP, subagents, material ingestion, LangGraph workflows, memory and UI.

# 2026-08-25 capability optimization pass

- Researched the eight Pi capability surfaces with Tavily CLI, Context7
  official documentation, and GitHub repository metadata. Added the detailed
  decision record at `docs/research/pi-capability-optimization-2026-08-25.md`.
- Skills now follow the official package shape and support `skill.json`,
  declared resources and the governed `read_skill_resource` tool. Deep
  Research's deterministic report validator runs before persistence.
- MCP discovery now consumes opaque cursor pages and preserves output schemas
  and annotations. The production environment still has no MCP server, so no
  external MCP capability was silently enabled.
- Updated the Pi runtime contract panel, subagent active polling, Tavily
  search depth/topic fields, remote Content-Disposition filename handling, and
  user-isolated Mem0 assistant entities.
- A real Tavily smoke initially exposed a Hikari routing bug: both base URL
  variables were present and the root-domain value won, producing `/search`
  404. The adapter now prefers the configured `/api/tavily` base and appends
  `/search`; a real `site:gov.cn 常州 招标 信息化` request returned three sources.
- Verification: API focused suites passed (`63` tests), Worker full suite
  passed (`197`), Pi tests passed (`14`), Web full suite passed (`167`) and
  Web/Pi builds passed. One legacy API streaming quota test is not suitable
  for a live Pi sidecar in the local suite and was excluded from the focused
  gate; it was not counted as a product pass.

# 2026-08-25 live agent environment panel

- Added a Codex-style Agent environment panel to the Agent workspace using the
  installed shadcn `Card`, `Badge`, `ScrollArea`, `Separator`, `Collapsible`,
  `Button`, and mobile `Sheet` components.
- The panel reads the Pi runtime contract and `/runtime/runs` API, refreshes
  live runs every four seconds, links each run to the Run Center, and shows
  real Skill resource and MCP registration state. It has no static run counts.
- Desktop and Pixel 7 Playwright acceptance passed `8/8`; Web full suite now
  passes `168` tests. A legacy deep-research fixture was updated to assert the
  new source count wording while retaining compatibility with older traces.

- Ran `git diff --check`; no whitespace errors were reported. This was a
  documentation/architecture baseline pass and did not claim that the full
  application test suite was rerun.

## 2026-08-19

- Promoted the Pi timeline, passive wake, subagent paging, specialized deep
  research projection, and pi-ai model catalog release candidate to
  `bidpilot.rglens.com`. Production readiness, migrations, and LangGraph
  checkpoint initialization passed before the API, Worker, Pi sidecar, and Web
  containers were replaced; the public Web and API health endpoints returned
  HTTP 200 afterward.
- Provisioned an isolated Enterprise demo workspace for `ztlh788@gmail.com`
  (`leho`) with one real member, three projects, five source documents, five
  knowledge chunks, fifteen requirements, one radar source and subscription,
  nine notices and matches, four deliverables, approval/runtime history, and an
  immutable exported artifact. The seed is idempotent and does not copy another
  user's model credentials.
- Production pi-ai catalog acceptance returned 40 providers and 1,267 models.
  The account can use the platform DeepSeek V4 Flash runtime immediately and
  may configure its own provider through the same native catalog.
- Executed one real read-only Pi Assistant turn through the public SSE endpoint
  for the seeded medical-data project. The run (`25453320-cf66-417e-9c1c-4979afa6f6e7`)
  persisted 21 runtime events, completed successfully, and produced a concrete
  readiness assessment from project documents, requirements, evidence, and
  deliverables. The public export API then generated and downloaded a 37,353
  byte DOCX successfully.

- Removed the visible synthetic "continue background task" turn. Background
  completion now resumes Pi through an exact-source, signed and idempotent
  system wake; the browser only refreshes the already open conversation.
- Subagent delegation no longer waits inside the Pi bridge request. It returns
  durable child run IDs immediately so SSE can expose queued/running/terminal
  children while Worker executes them.
- Skill-authored presentation metadata now groups deep research into one
  specialized staged runtime without tool-name or message keyword matching.
  Ordinary web searches remain chronological rows, while parallel subagents
  use the paged child-run projection.
- Focused API runtime acceptance passed 22 tests and Worker wake/outbox/subagent
  acceptance passed 12 tests against the dedicated local PostgreSQL test
  database.
- Agent-workspace Playwright regression passed 8/8 across desktop Chromium and
  Pixel 7, covering the composer boundary, structured canvas, paged subagents,
  and the single deep-research runtime projection.
- Assistant frontend projection now preserves Pi event chronology across
  multiple tool bursts in one model turn instead of attaching all execution to
  the first timeline group.
- Durable subagent runs now inherit their parent message/execution group in live
  and replayed conversations. Parallel children render through a responsive
  paged viewer with live status and expandable tool steps; all levels remain
  collapsed by default.
- Removed legacy public-narration phrase filtering from the event adapter. UI
  projection is based on event IDs, sequence, and parent/child run relations,
  never content keyword matching.
- Focused web regressions cover chronological grouping, live waiting feedback,
  nested child runs, and three-child pagination.
- Agent-workspace Playwright acceptance passed on desktop Chromium and Pixel 7:
  the parent run is collapsed initially, child pages switch from `1 / 3` to
  `2 / 3`, the selected child exposes its expandable public execution steps,
  and the viewer stays within the mobile viewport.

- Formal-release candidate uses Pi for all new Assistant turns; lexical routing
  and the retired Python Harness are not production fallbacks.
- Golden bid-response path passed 10/10 with company-evidence separation,
  requirement extraction, evidence mapping, human review, immutable redraft,
  DOCX export, retry recovery, and traceable material manifests.
- Live Chromium validation passed the user journey from registration through
  project creation, ingestion, Assistant status inspection, drafting, approval,
  and download.
- Release rehearsal passed with API `822 passed / 60 skipped`, Worker `194
  passed`, Web `154 passed`, Pi sidecar `12 passed`, mobile Chromium `5 passed`,
  and the local load smoke at zero failures.
- Long-section drafting completion budget increased from 4,096 to 16,000 after a
  real provider truncation was reproduced; regression tests cover the contract.
- Next handoff entry: use the production deployment record and post-release smoke
  evidence as the source of truth before beginning new product work.
- The first production promotion attempt correctly failed readiness because the
  legacy outer Compose topology did not contain `pi-agent`. The deploy helper is
  now fail-closed for Pi: it requires the complete versioned production Compose
  and the dedicated internal bridge secret instead of partially replacing API,
  Worker, and Web against an incomplete topology.
- The production-readiness contract itself now recognizes only `pi` as the
  canonical Assistant engine and validates the bridge secret length; the stale
  Harness-only release assertion and its fixtures were removed.

## 2026-08-22

- Reorganized the active web application boundaries without changing API
  behavior: product screens now live under `apps/web/src/features/workbench`,
  while Pi Agent state, runtime event projection, transcript mapping, and UI
  live under `apps/web/src/features/agent/{state,runtime,components}`.
- Quarantined the unused assistant-ui experiment under
  `apps/web/src/features/agent/legacy`; it is not imported by the active
  routes or production shell. This is a frontend-only compatibility boundary,
  not a second Assistant runtime.
- Removed `v2` from active workbench filenames, exports, CSS class names, and
  route imports. The UI consumes the public runtime event contract and uses
  event identity/sequence/parent relations for projection; no message text or
  tool-name substring is used to infer execution state.
- Verification after the move: TypeScript `--noEmit` passed, Web Vitest passed
  (`36` files, `163` tests), and the Vite production build passed. The build
  still reports existing large-chunk warnings; this cleanup did not change
  bundling policy.

## 2026-08-22 backend runtime boundary cleanup

- Added `app.runtime.model` as the canonical provider boundary for API,
  Worker, scripts, and the signed Pi bridge. `app.agent.llm` remains a
  compatibility implementation during the migration window; new runtime-owned
  code does not import it directly.
- Added `app.runtime.conversation` for bounded authorized transcript, memory,
  and attachment projection. The Pi wake path no longer imports the old
  Operator graph or `operator_adapter` to build context.
- Made historical Operator/LangGraph imports lazy inside the compatibility
  branch of `operator_adapter.py`. Importing the production Pi adapter and
  bridge no longer initializes `operator_graph` or `harness_loop`.
- Verification: API/Worker Ruff checks, API compileall, and a Python import
  isolation probe passed. Runtime pytest remained gated because the repository
  requires an explicitly configured dedicated PostgreSQL database ending in
  `_test`; no business database was substituted.
