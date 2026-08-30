# Progress Log

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
