# Current Execution State

## Current Tasks

- [x] 把项目、资料、需求、知识、响应、评审和交付物串成项目优先的用户流程；项目关联入口不再无条件跳转到 Agent。
- [x] 使用现有 Kiranism/Base UI 组件完成资料上传、真实解析/索引状态、章节起草、人工审核和 DOCX/PDF 导出。
- [x] 完成公网登录、项目创建、三类资料上传、Worker 解析索引、三章真实起草、审核批准和 DOCX/PDF 导出记录验收。
- [ ] 生成五章全部批准的最终文件：当前验收账户 starter 官方工作流额度为 `3/3`，剩余两章被后端正常拒绝；需要管理员套餐 entitlement 或账户已有 BYOK MiMo 配置后，再按同一页面流程完成最后两章。
- [x] 生产运行时切换到 MiMo Worker 合同：关闭 Worker 结构化调用的隐藏思考并使用 `max_completion_tokens`；第二次公网起草不再出现结构化响应错误。
- [x] 公网部署 `eceb42c4088e5886017615c70b25ac314df36155`，完成 readiness、migration、checkpoint、健康检查和 Docker 垃圾清理。
- [ ] Supabase 托管迁移：当前 `bidpilot` 项目状态为 `INACTIVE`，且本机只有 Management PAT，没有数据库 Session Pooler 密码或 Storage S3 access key/secret；恢复项目并补齐连接凭据后再做备份迁移、对象校验和完整回归。
- [ ] 商业 GA 之外的长期事项：隐藏回归数据集/质量证据、恢复演练、告警和支付运营；这些不阻塞本项目作为个人面试展示项目的公网演示，但不能被表述为企业商业 GA。

## 2026-09-01 Kiranism Next migration

- active branch: `codex/kiranism-bidpilot` in the isolated `BidPilot-kiranism`
  worktree
- Kiranism dashboard source is now the Next/shadcn/Base UI frontend base
- FastAPI, Worker, PostgreSQL and the Pi sidecar remain the business/runtime
  authority
- Next Route Handlers forward same-origin REST/SSE requests and attach the
  HttpOnly FastAPI access cookie
- public landing, auth, dashboard, project, requirements, knowledge, run,
  deliverable, review, member, account, admin and provider routes are present
- local direct-process verification: FastAPI on `127.0.0.1:8000`, Pi on
  `127.0.0.1:8787`, Next on `127.0.0.1:3300`, isolated SQLite demo account and
  workspace, 14 authenticated user routes plus public pricing/docs and admin
  denial checks passed
- local dependency boundary: PostgreSQL/Redis/MinIO/Worker are not running on
  this machine; SQLite validation covers UI/API contracts only and does not
  claim queue, indexing, object-storage or PostgreSQL/pgvector parity
- local Agent transport: `DOCPILOT_LOCAL_DIRECT_ASSISTANT=true` invokes the
  existing queued Pi executor in-process, registers the same cancellation
  control and preserves the durable runtime event contract; it is not a second
  model runtime or a keyword router
- Agent UI boundary: the full-page composer is statically imported to avoid a
  stale route-manifest chunk taking down `/agent`; at `1024px` and below the
  environment panel is an on-demand shadcn Sheet, while the message thread and
  composer remain independently sized and scrollable
- Product data motion: dashboard/workbench data pages use the shared
  `LiveSyncStatus` with query freshness and manual refresh. Radar uses a real
  30-second query poll and Recharts transition; no dynamic indicator is backed
  by fabricated data or keyword inference.
- Agent theme boundary: the legacy workspace and Pi transcript styles inherit
  Kiranism semantic theme tokens for primary, background, card, muted, border,
  ring and destructive states. They do not force a light palette or use the
  old purple/Claude hardcoded UI colors.
- Public marketing boundary: the landing page keeps the reused SaaS Boilerplate
  section composition but exposes only BidPilot product copy and uses the same
  active theme tokens as the app shell. Its mobile menu, FAQ and CTA links are
  browser-checked.
- Kiranism's existing `ThemeSelector` is exposed in the authenticated Header
  beside the light/dark mode toggle. It lists the upstream registered themes and
  persists the selection through the active-theme cookie; the same official
  controls are exposed in the public landing, docs and pricing navigation. No
  custom color picker or duplicate palette exists.
- Local direct-process startup profiles load the same local environment source
  and align `DOCPILOT_PI_INTERNAL_SECRET` between API and Pi before browser
  acceptance. A real local `你好` turn completed as `succeeded / pi` after this
  correction.
- Local direct-process Agent streaming now forwards each native Pi SSE event
  through an in-memory queue while the executor is running. It no longer waits
  for the full Pi turn and then replays the completed timeline, which had made
  the first visible text appear as one large burst. The stream still preserves
  Pi's provider delta boundaries; it does not split text or infer intent from
  keywords.
- A 2026-09-02 local timing probe measured the corrected API path at about
  `0.17s` to the first SSE frame and `2.20s` to the first visible assistant
  delta, with the Next proxy retaining `text/event-stream` and chunked
  delivery. The local environment is currently configured for DeepSeek, not
  MiMo; MiMo latency is therefore not claimed until its server-side profile is
  actually configured.
- remaining release gates: run the dedicated PostgreSQL/Redis/MinIO Worker
  acceptance environment, then obtain explicit production promotion approval

## Goal

Give future implementation sessions one quick status file so work can resume without reconstructing progress from scratch.

## Current status

- repository state: Pi-based assistant migration and governed subagent closure implemented locally; public `/assistant/stream` is Pi-only
- implementation state: API/Worker/Pi contracts cover run-scoped bridge auth, durable parent/child runs, foreground/background delegation, safe user projection, bounded terminal waits, replay, cancellation, and fail-safe SSE errors; frontend renders nested chronological child activity without exposing private tool payloads
- browser acceptance: authenticated Playwright run completed two independent read-only child tasks in parallel; the parent waited in the same turn and summarized real project/skill results with zero console errors
- focused checks: API Pi/runtime contract suite `22 passed, 29 skipped`; Worker subagent/event suite `8 passed`; frontend assistant/timeline/event suite `57 passed`; Pi package tests `12 passed` and build succeeds
- legacy test suites that assert the retired lexical/deterministic/Python Harness endpoint are explicitly skipped or require migration; they are not production contracts
- active phase: `Pi production convergence` — local closure complete; public deployment remains a separate release decision
- next intended workstream: real-provider/staging soak, load and failure-recovery evaluation, then release promotion

## Phase 0 completion summary

- Task 1: repository layout and root tooling — done
- Task 2: React workbench shell (`apps/web`) — done
- Task 3: FastAPI service and database skeleton (`services/api`) — done, with Alembic migrations working against live Postgres
- Task 4: local infrastructure and worker skeleton — done, compose.yml includes postgres, redis, minio; worker ping test passes
- Bug fixes applied: db.py port corrected to 5433, alembic env.py wired to models, migration 054f06186512 now creates/drops project table, .gitignore expanded

## Phase 1 completion summary

- Task 1: project workspace CRUD — done (POST /projects, schemas, router, test, frontend stub)
- Task 2: bundle upload registry and ingest scheduling — done (POST /bundles, schemas, router, test, worker ingest stub)
- Task 3: evidence-backed section drafting — done (POST /drafting/sections, schemas, router, test, worker drafting stub, frontend stub)

## Start here next

1. read `docs/development/local-environment-baseline.md`
2. read `docs/development/agent-execution-manual.md`
3. choose the next deepening target (persistence, Celery wiring, auth middleware, or UI integration)

## Do not skip ahead yet

All planned phases are complete. Next work should deepen existing stubs rather than add new surface area.

## Phase 2 completion summary

- Task 1: section review workflow — done (POST /review/decisions, schemas, router, test, frontend stub)
- Task 2: audit events and trace correlation — done (GET /audit/events, service, router, test)
- Task 3: deployment automation and smoke checks — done (CI workflow, smoke.sh, OpenAPI smoke test)

## Phase 3 completion summary

- Task 1: auth and RBAC baseline — done (GET /auth/me, schemas, service, router, test)
- Task 2: backup/restore scripts and release automation — done (backup-db.sh, restore-db.sh, release.yml, health contract test)
- Task 3: operational dashboards — done (GET /ops/runtime-summary, router, test, frontend stub)

## Phase 4 completion summary

- Task 1: scenario package registry — done (GET /scenarios, registry, router, test)
- Task 2: scenario template binding — done (resolve_default_template, test, frontend stub)
- Task 3: BidPilot compatibility regression guard — done (contract test, ADR 0002)

## Deepening: persistence layer

- Expanded SQLAlchemy models to all 14 tables from data-model.md
- Generated migration `be4fa2116b5e_add_full_domain_model` (applied successfully)
- Added `repository.py` + `service.py` to projects, bundles, audit, review, drafting modules
- Wired routers through `Depends(get_db)` → service → repository → PostgreSQL
- Slug generation with uniqueness check for projects
- All 13 tests pass against live Postgres
- Remaining in-memory stubs: auth (no DB table), ops (read model), scenarios (static registry)

## Deepening: Celery wiring + new endpoints

- Created `celery_app.py` in worker with Redis broker
- Registered `worker.ingest_bundle` and `worker.draft_section` Celery tasks
- Created `celery_client.py` in API for task dispatch
- Bundle creation now dispatches `worker.ingest_bundle` async task
- Drafting endpoint now dispatches `worker.draft_section` async task
- Ops runtime-summary now queries real `execution_run` stats from DB
- Added `GET /projects/{project_id}` endpoint
- Added `GET /bundles?project_id=` endpoint
- All 16 tests passing (13 API + 3 worker)

## Deepening: new domain modules

- Added `deliverables` module: POST /deliverables, GET /deliverables?project_id=, POST /deliverables/sections, GET /deliverables/{id}/sections
- Added `execution` module: GET /execution/runs/{id}, GET /execution/runs?project_id=
- Added `documents` module: GET /documents?bundle_id=
- All modules follow repository → service → router layer pattern
- 15 API tests + 3 worker tests = 18 total passing

## Deepening: worker DB state + requirements + providers + auth

- Worker tasks now update DB: `ingest_bundle` sets `bundle.ingest_status = "ingested"`, `draft_section` sets `run.status = "succeeded"` with timestamps
- Worker has its own `db.py` + `models.py` for DB access
- Added `requirements` module: POST /requirements, GET /requirements?project_id=
- Added `providers` adapter module: `llm.py` (stub LLM generate), `parser.py` (stub document parse)
- Created `packages/contracts/tasks.py` with shared task name constants
- Added `User` model + migration `2f358b58a579_add_user_table`
- Full JWT auth: POST /auth/register, POST /auth/login, GET /auth/me with Bearer token
- GET /auth/me falls back to dev user when no token provided
- 19 API tests + 3 worker tests = 22 total passing

## Deepening: retrieval + evidence + worker refactor

- Added `retrieval` module: POST /retrieval/search with ILIKE full-text search on knowledge_chunk
- Added `evidence` module: GET /evidence?project_id= listing evidence items
- Refactored worker into `adapters/` + `execution/` submodules per architecture doc
- Worker `adapters/parser.py`: parse_bundle_documents + store_chunks (stub)
- Worker `adapters/llm.py`: draft_section with evidence injection (stub)
- Worker `execution/ingest.py`: run_ingest pipeline (parse → store chunks → update status)
- Worker `execution/drafting.py`: run_draft pipeline (retrieve evidence → LLM → write section version → update status)
- Worker models expanded: SourceDocument, KnowledgeChunk, DeliverableSection, SectionVersion
- Tasks now delegate to execution modules instead of inline logic
- 22 API tests + 3 worker tests = 25 total passing

## Deepening: frontend integration

- Installed TanStack Query, React Router, Tailwind CSS v4, shadcn/ui, Lucide React
- Created API client (`src/lib/api.ts`) with typed fetch functions for all endpoints
- Built `ProjectListPage`: list projects, create new project with form
- Built `ProjectDetailPage`: bundles (register + list), deliverables (create + list), draft section, execution runs table
- App shell with BrowserRouter + QueryClientProvider + header nav
- shadcn/ui components: button, card, input, label, table, badge
- Frontend builds successfully with `vite build`
- 1 frontend test passing (app shell renders)

## Deepening: governance RBAC and browser smoke guardrails

- Added Playwright E2E smoke setup for the web app with always-runnable unauthenticated checks and opt-in seeded demo flow
- Added governance RBAC guard: `require_admin` now protects audit and ops routes while dev fallback remains admin
- Added API regression tests proving member users receive `403 Admin role required` for audit and ops endpoints
- Added frontend role helper so non-admin users do not see Audit/System project detail tabs or trigger governance queries
- Added frontend permission tests for admin, non-admin, and missing-user role cases
- Ran the opt-in seeded Playwright demo flow with local API + seeded data (`E2E_DEMO=1`), covering login, seeded project navigation, governance tabs, review tab, and audit tab

## Deepening: load smoke guardrail

- Added dependency-free `scripts/load_smoke.py` for short local API concurrency checks
- Added tests for load summary metrics, error-rate thresholding, and P95 thresholding
- Documented the release-candidate load smoke command in ops and quality docs
- Verified the load smoke against local API: 40 requests, 0 failures, aggregate P95 under 100ms

## Deepening: monitoring dashboard baseline

- Added a focused `RuntimeSummaryCards` component for the Project Detail `System` tab
- Added frontend tests for healthy, attention-needed, and loading runtime summary states
- Updated the seeded demo Playwright flow to search for the seeded project when local DB has more than 50 projects and to verify the System tab renders `System Status`
- Verified frontend typecheck, frontend unit tests, build, and seeded demo E2E after the dashboard change

## Deepening: production readiness gate

- Added `scripts/production_readiness.py` to validate production deployment environment variables without connecting to external services
- Added tests covering missing variables, development defaults, localhost endpoints, auth enforcement, and valid production-shaped config
- Replaced the release workflow placeholder with a production readiness checker step backed by GitHub secrets
- Updated deployment, release, and configuration docs to require the readiness gate before production promotion

## Deepening: release rehearsal gate

- Added `scripts/release_rehearsal.py` with a dry-run default and `--run` execution mode
- Core rehearsal covers API migrations, API and Worker Ruff checks, API and Worker tests, frontend typecheck, frontend unit tests, and frontend build
- Optional flags add browser smoke, API load smoke, and production readiness checks when the required local services or secrets are available
- Added tests for rehearsal step generation and dry-run rendering
- Added `docs/ops/release-rehearsal-runbook.md` and linked it from deployment and release docs
- Verified the core rehearsal with `python scripts/release_rehearsal.py --run`; it completed migrations, API and Worker Ruff checks, API and Worker tests, frontend typecheck, frontend unit tests, and frontend build successfully

## Deepening: backup/restore and pilot readiness

- Updated `scripts/backup.py` with testable `pg_dump` and `psql` command builders plus `--dry-run` support
- Added tests for PostgreSQL URL parsing, backup command construction, and restore command construction
- Added `docs/ops/backup-restore-drill.md` with staging restore drill steps and RPO/RTO references
- Added `docs/product/pilot-readiness-checklist.md` covering product, operational, and commercial pilot gates
- Updated release/deployment docs to require backup dry-run and staging restore drill confirmation before production promotion

## Deepening: pilot bootstrap admin

- Added `bootstrap_admin_command` to `app.auth.service` with idempotent create, already-admin, and promote paths
- Added `services/api/tests/auth/test_bootstrap_admin.py` covering created, already_admin, refused promotion, and promoted with flag
- Added `scripts/bootstrap_admin.py` CLI with `--email`, `--display-name`, `--password`/env/prompt, and `--promote`
- Added `docs/ops/first-run-pilot-bootstrap.md` with step-by-step pilot environment bring-up
- Updated `docs/product/pilot-readiness-checklist.md` to require first admin provisioning

## Deepening: CI and release workflow hardening

- Added frontend typecheck and unit test steps to `.github/workflows/ci.yml` before the build step
- Expanded `.github/workflows/release.yml` from a single readiness gate to three parallel jobs: `api-test`, `frontend-build`, and `production-readiness`
- Both workflow YAML files validated successfully

## Deepening: commercial packaging — pricing page

- Added `features/pricing/pricing-page.tsx` with three tiers (Starter, Professional, Enterprise) using shadcn Card, Badge, Separator, and Button
- Added `features/pricing/pricing-page.test.tsx` with 3 tests covering tier names, recommended badge, and feature lists
- Wired `/pricing` route in `app.tsx` with sidebar nav item (CreditCardIcon)
- All frontend tests pass (11 total); typecheck and build succeed

## Deepening: commercial front door — landing hero + onboarding wizard

- Added `features/landing/landing-page.tsx` with hero section (headline, sub-headline, CTA to signup/pricing, 3 feature highlight cards) using shadcn Card, Badge, Button
- Added `features/landing/landing-page.test.tsx` with 3 tests
- Added `features/onboarding/onboarding-wizard.tsx` with 3-step wizard (welcome, create project, all set) using shadcn Card, Button, Progress
- Added `features/onboarding/onboarding-wizard.test.tsx` with 3 tests
- Restructured routes: `/` → public LandingPage, `/projects` → auth-gated ProjectListPage, `/pricing` → public PricingPage
- Updated `login-form.tsx` and `signup-form.tsx` to navigate to `/projects` after auth
- Updated `app.test.tsx`, `auth.spec.ts`, `demo.spec.ts` for new route structure
- All frontend tests pass (17 total); API tests pass (51 total); typecheck and build succeed

## Deepening: subscription model + onboarding wiring

- Added `Subscription` model to `app/models.py` with `user_id` (unique FK), `plan` (default starter), `status` (default active), `stripe_customer_id`, timestamps
- Added `plan` field to `CurrentUser` schema (default "starter"), auto-populated from subscription table
- Registration auto-creates starter subscription; admin bootstrap auto-creates professional subscription
- Added `GET /auth/subscription` endpoint returning `SubscriptionRead`
- Added `SubscriptionRead` type and `getSubscription()` to frontend API client
- PricingPage now highlights current plan tier with "Current Plan" badge and ring border
- Wired `OnboardingWizard` into `ProjectListPage` — shows when zero projects and onboarding not yet completed (localStorage persisted)
- Alembic migration `27bbad823c47_add_subscription_table.py` generated and applied
- All tests pass: API 54, frontend 17; typecheck and build succeed

## Deepening: plan limit enforcement + account plan display

- Added `PLAN_LIMITS` constants: starter=3 projects, professional=-1 (unlimited), enterprise=-1
- Added `check_plan_limit()` to `auth/service.py` — raises ValueError when plan limit would be exceeded
- Wired `check_plan_limit` into `POST /projects/` with `require_auth` — starter users get 403 on 4th project
- Dev user (professional plan) bypasses limit; existing tests unaffected
- AccountPage profile section now shows plan badge (CreditCardIcon) and upgrade CTA for starter users
- All tests pass: API 59, frontend 17; typecheck and build succeed

## Deepening: quota UI + admin plan upgrade

- ProjectListPage shows quota hint card for starter users: "X of 3 projects remaining" or "Project limit reached" with upgrade CTA
- Added `update_subscription_command()` to auth service with plan validation (starter/professional/enterprise) and upsert logic
- Added `PATCH /auth/subscription` endpoint (admin-only via `require_admin`) for manual plan upgrades
- Added `SubscriptionUpdate` schema with `user_id` and `plan` fields
- AccountPage shows plan badge and upgrade CTA for starter users
- All tests pass: API 63, frontend 17; typecheck and build succeed

## Deepening: Stripe integration + checkout flow + admin controls

- Created `app/adapters/stripe_adapter.py` — wraps Stripe checkout session creation and webhook verification behind env-var-gated adapter
- Created `app/billing/router.py` with `POST /billing/checkout` (creates Stripe checkout session) and `POST /billing/webhook` (handles checkout.session.completed → upgrade, subscription.deleted → downgrade)
- Billing router registered in `main.py` as public (webhook has no auth, checkout uses require_auth internally)
- PricingPage CTA buttons now trigger checkout: Professional/Enterprise → Stripe redirect, Starter → /login, unauthenticated → /login
- Graceful fallback when Stripe not configured (501 → toast "Contact your admin")
- Project creation 403 error now shows upgrade toast with "Upgrade" action → /pricing
- AccountPage admin users get plan change dropdown (Select component) calling `PATCH /auth/subscription`
- Frontend `api.ts` added `createCheckout()`, `updateSubscription()`, `CheckoutResult` type
- All tests pass: API 70, frontend 17; typecheck and build succeed

## Deepening: SMTP email infrastructure

- Fixed `SmtpEmailBackend` to support port 465 (SMTP_SSL) in addition to port 587 (STARTTLS), required for QQ/Foxmail
- Added `python-dotenv` dependency and `load_dotenv()` call in `main.py` to load `.env` file
- Created `.env.example` template with all required environment variables
- Configured Foxmail SMTP (`smtp.qq.com:465`) with real credentials in `.env`
- Fixed test conftest to reset `AUTH_REQUIRED=False` when `.env` sets `DOCPILOT_AUTH_REQUIRED=true`
- Verified real email delivery: test email sent successfully to `docpliot@foxmail.com`
- All tests pass: API 95, frontend 17; release rehearsal passes

## Deepening: enterprise email verification enforcement

- `login_command` now rejects unverified users with `ValueError("Email not verified...")`
- `refresh_token_command` also rejects unverified users
- Login endpoint returns 403 with structured `{"error": "email_not_verified", "message": ..., "email": ...}` for unverified users
- `ResendRateLimiter` added: 3 resends per email per hour (anti-abuse)
- `POST /auth/resend-verification?email=...` accepts email param without auth (no user enumeration)
- `POST /auth/users/{user_id}/verify` admin endpoint for manual verification
- `admin_verify_user_command` added to auth service
- Bootstrap admin users auto-verified (`email_verified=True` on creation)
- Frontend: registration no longer auto-logs in; navigates to `/verify-email-prompt`
- Frontend: new `VerifyEmailPromptPage` with resend button
- Frontend: new `VerifyEmailPage` auto-verifies token from email link
- Frontend: login form shows amber "Email not verified" banner with resend button on 403
- Frontend: `resendVerification()` API accepts optional email param; `adminVerifyUser()` added
- 11 new tests covering: login rejection, post-verification login, rate limiting, admin verify, bootstrap auto-verify, user enumeration prevention
- All existing tests updated to verify email after registration
- All tests pass: API 106, frontend 17; typecheck and build succeed

## Deepening: user-customizable AI API providers

- Added `ProviderConfig` model (id, user_id, provider_type, api_key, api_url, model, label, is_active) with Alembic migration `8f929f4a7307`
- Added CRUD endpoints at `/auth/me/providers` (GET list, POST create, GET by id, PUT update, DELETE, POST test-connection)
- Created worker `provider_registry.py` — resolves user provider configs from DB by id or by active status
- Created `services/worker/app/adapters/anthropic_llm.py` — real Anthropic Messages API adapter with env-var/DB-provided credentials, falls back to stub
- Refactored `services/worker/app/adapters/llm.py` to accept optional `provider_config` dict (api_key, api_url, model)
- Refactored `services/worker/app/execution/drafting.py` to resolve `provider_config_id` from DB and route to OpenAI or Anthropic adapter based on `provider_type`
- Updated Celery task `worker.draft_section` to accept and pass `provider_config_id` through kwargs
- Updated frontend drafting schemas (`DraftSectionRequest`, `RedraftSectionRequest`) to include optional `provider_config_id`
- Added `ProviderSettingsPage` at `/settings/providers` — card grid, add/edit dialog, test connection, active toggle
- Frontend API client types and functions for all provider CRUD + test-connection
- All tests pass: API 141/141, frontend 26/26, TypeScript zero errors

## Pilot readiness validation

- All automated checks green: API 141/141, frontend 26/26, Playwright E2E 15/15, typecheck + build pass
- MinIO credentials fixed in `.env` and `.env.example` (docpilot/docpilot123)
- Project creation now navigates to detail page (`project-list-page.tsx` onSuccess)
- E2E full flow test fixed: register bundle → expand accordion → upload file
- Auth E2E tests updated for email verification flow: separate `request.newContext` for admin API calls
- Admin/member governance E2E tests updated for email verification flow
- Production readiness gate: all env vars configured; localhost infra expected for local dev, must switch for real deployment
- Commercial readiness documented in `docs/product/pilot-commercial-readiness.md`: data handling, support tiers, pricing, success criteria
- Non-developer demo guide created at `docs/product/non-developer-demo-guide.md`
- Known limitations updated: email verification now enforced, SMTP configured, Aliyun DashScope provider configured
- User-customizable API providers implemented: users can bring their own OpenAI-compatible or Anthropic/Claude API keys via settings UI
- Remaining: non-developer demo walkthrough (requires human), [OWNER] fields in commercial readiness doc

## Update rule

Update this file whenever one of these changes:

- the active phase changes
- implementation meaningfully starts or finishes a major workstream
- the next recommended entry point for the following session changes

## Short note for future agents

The documentation set is meant to drive continuous implementation. If code and docs diverge, fix the docs or the implementation before continuing broader work.

## 2026-08-19 Pi runtime release candidate

- New Assistant turns use the Pi `AgentSession` sidecar exclusively. The retired
  deterministic and lexical Harness contracts remain only as explicitly skipped
  historical tests; they are not a production fallback.
- Business capabilities remain server-owned and are projected into Pi as dynamic
  tool schemas. Tool execution, tenant checks, approvals, quotas, audit and
  durable run events continue through the governed API bridge.
- Foreground child agents can run independent read-only work in parallel and are
  joined into the parent turn. Background child agents are queued through the
  durable worker outbox and surface as parent-child run history.
- The Agent timeline maps transcript and durable runtime events into one nested,
  chronological public view. Internal provider reasoning and raw bridge payloads
  are not exposed to users.
- Release-candidate verification on Windows:
  - API: `822 passed, 60 skipped, 0 failed`
  - Worker: `194 passed, 0 failed`
  - Pi sidecar: `12 passed, 0 failed`; TypeScript build passed
  - Web: `154 passed, 0 failed`; Vite production build passed
- The fixture-source hash check now canonicalizes line endings before hashing so
  the same reviewed evaluation fixture is valid on Windows and Linux.
- Production configuration must set `DOCPILOT_ASSISTANT_ENGINE=pi` and keep the
  Pi internal bridge secret out of source control and user-visible events.

### Lexical-routing purge

- `/assistant/stream` is now an unconditional Pi entry point. The runtime engine
  can no longer be selected by an environment alias or by message text.
- New turns in `operator_adapter.py` create `engine="pi"` runs and call Pi
  directly; the unreachable legacy graph branch was removed from that path.
- Skill selection is semantic and progressive through Pi's trusted resource
  catalogue plus `read_skill`; no user-message keyword table is present.
- Source-contract tests reject reintroduction of confirmation/cancellation
  phrase routers, keyword trigger tables, old intent classification, or the
  retired Python loop in the public Pi path.
- Real local black-box checks covered: a no-tool answer (zero tools, one terminal
  event), bounded read-only opportunity research (only `web_search`, no write),
  and one structured `create_project` call (one success, no retry loop).

## 2026-08-19 formal-release acceptance

- The isolated golden path passed all 10 stages against real PostgreSQL, Redis,
  Celery, object storage and the configured model provider. It created one
  project with role-aware buyer and supplier bundles, ingested three documents,
  extracted 32 buyer requirements, kept supplier identity material out of the
  requirement set, verified evidence coverage, exercised reject/redraft/approve,
  exported a 38,474-byte DOCX, retried a controlled failed run, and pinned the
  material manifest plus checksum. Redacted evidence is retained locally at
  `output/release-evidence/formal-release-golden-path.json`.
- The live browser chain passed registration, administrator verification,
  login, project creation, tender upload, parse/index completion, a Pi Assistant
  project-status turn with a terminal event, deliverable and section creation,
  model-backed drafting, human approval, and DOCX download.
- Web verification passed 154 unit tests, lint with no errors, TypeScript/Vite
  production build, five mobile Chromium scenarios, and the live desktop
  Chromium workflow. The existing test-only React `act` warnings and large
  Assistant chunk warning remain performance/test-hygiene follow-ups, not
  correctness failures.
- Worker drafting now budgets 16,000 completion tokens so providers that account
  for reasoning and visible output in one completion do not truncate long bid
  sections at the former 4,096-token ceiling. The adapter and drafter regression
  suite passed 46 tests.
- `.env.local-runtime` is explicitly ignored. Release evidence contains no
  environment values or credentials.
- The repeatable release rehearsal passed migrations, API and Worker static
  checks and full suites, frontend typecheck/tests/build, and a 40-request API
  load smoke with zero failures and 90.01 ms aggregate p95 latency.
