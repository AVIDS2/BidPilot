# Progress Log

## 2026-08-22

- Added the official `mem0ai==2.0.18` adapter for optional long-term user
  profile memory. The adapter uses Context7-verified `MemoryClient` APIs,
  organization-scoped filters, bounded timeout/fail-open recall, asynchronous
  Worker capture, local idempotency ledger, and scoped account deletion. It is
  disabled by default until the deployment injects `DOCPILOT_MEM0_API_KEY`.
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
