# DocPilot VPS Pilot Productionization Design

## Status

- Status: draft for owner review
- Date: 2026-06-15
- Source analysis: `docs/product/commercial-launch-gap-analysis.md`
- Scope: controlled VPS pilot, not full paid public launch

## Goal

Make the current DocPilot/BidPilot product safe and repeatable to deploy on the VPS for a controlled external pilot with named users.

The target outcome is a public HTTPS deployment where a pilot user can register or be invited, verify email, create a BidPilot project, upload documents, run one limited AI drafting workflow, review output, export a deliverable, and where the operator can monitor, back up, restore, and disable risky paths.

## Non-goals

This spec does not ship full public self-serve commercialization.

Out of scope for this phase:

- full Stripe production billing;
- invoice, refund, renewal, failed-payment, and billing portal flows;
- enterprise SSO or MFA;
- multi-region or Kubernetes deployment;
- unlimited public registration;
- new scenario packages beyond BidPilot;
- custom workflow builder features;
- perfect DOCX template fidelity;
- real-time collaborative editing.

## Operating assumptions

- Deployment target is the existing VPS: `root@38.14.254.50`.
- Public domains are already available:
  - `bidpilot.rglens.com` primary;
  - `api.bidpilot.rglens.com` for API;
  - `pay.rglens.com` reserved for future payment flows.
- The initial production shape is single-node VPS deployment.
- The current `compose.yml` only runs infrastructure services: PostgreSQL, Redis, and MinIO.
- API, worker, and web production packaging still need to be defined.
- Official provider keys stay server-side.
- User-supplied provider keys are stored encrypted with `DOCPILOT_SECRETS_KEY`.
- Aliyun Bailian/DashScope IP allowlist should include only the VPS egress IP and any explicitly approved local test IP.

## Release target

The pilot deployment should support:

- HTTPS web UI;
- HTTPS API;
- protected API routes with `DOCPILOT_AUTH_REQUIRED=true`;
- SMTP-backed email verification, password reset, and invitations;
- one server-side official AI provider for limited workflow drafting;
- encrypted BYOK storage;
- starter-user workflow trial limit;
- durable database, Redis, and object storage volumes;
- first-admin bootstrap;
- backup and restore rehearsal;
- end-to-end smoke validation.

## Architecture

### Environment model

The VPS pilot becomes a production-like environment, stricter than local development but smaller than full commercial production.

Local:

- can keep localhost defaults;
- may use stub or memory paths for debugging;
- may fall back to dev user when `DOCPILOT_AUTH_REQUIRED=false`.

VPS pilot:

- must not use localhost in user-facing links;
- must set `DOCPILOT_AUTH_REQUIRED=true`;
- must set durable `DOCPILOT_LANGGRAPH_CHECKPOINTER=postgres`;
- must inject real secrets through server environment or 1Panel secret configuration;
- must use HTTPS public URLs.

Future production:

- adds full billing, deeper observability, commercial support, and stricter customer data controls.

### Deployment topology

The recommended pilot topology is:

- PostgreSQL with pgvector;
- Redis;
- MinIO or S3-compatible object storage;
- FastAPI API service;
- Celery worker service;
- static Vite web build served by Nginx, Caddy, or 1Panel site hosting;
- reverse proxy handling TLS and routing:
  - web domain -> static web files;
  - `api.bidpilot.rglens.com` -> FastAPI API service.

This phase should stay single-node. The system should be container-friendly, but the minimum success criterion is a repeatable VPS deployment, not a platform migration.

### Runtime process model

API:

- `uvicorn app.main:app`;
- reads `services/api/.env` or injected environment;
- runs Alembic migrations before first use;
- exposes `/health` and admin-only detailed health routes.

Worker:

- Celery worker with Redis broker;
- shares database, Redis, object storage, provider, and encryption settings with API;
- uses postgres LangGraph checkpointer for durable workflow state.

Web:

- built with `pnpm --filter @docpilot/web build`;
- uses a production `VITE_API_URL=https://api.bidpilot.rglens.com`;
- served as static assets.

## Required code changes

### Production URL configuration

Problem:

- Email invitation links and billing checkout links still contain hardcoded localhost URLs.
- CORS currently allows only local Vite origins.

Design:

- Treat `DOCPILOT_APP_URL` as the canonical browser URL.
- Add `DOCPILOT_API_URL` if API-generated links need an API origin.
- Add `DOCPILOT_CORS_ORIGINS` as a comma-separated allowlist.
- Replace all production-facing hardcoded frontend URLs with `DOCPILOT_APP_URL`.
- Billing checkout success and cancel URLs should derive from `DOCPILOT_APP_URL`.
- Invitation links should derive from `DOCPILOT_APP_URL`.

Acceptance:

- Searching production code for `http://localhost:5173` should only find local docs, tests, or explicitly local defaults.
- A VPS environment with `DOCPILOT_APP_URL=https://bidpilot.rglens.com` sends email links to that origin.
- API CORS accepts the deployed web origin and still supports local development.

### Production readiness validation

Problem:

- The readiness script validates core secrets and localhost infrastructure but does not yet validate public URL settings, CORS origin settings, SMTP completeness, or durable LangGraph mode.

Design:

- Extend `scripts/production_readiness.py` to validate:
  - `DOCPILOT_APP_URL` exists and is HTTPS for production;
  - `DOCPILOT_CORS_ORIGINS` includes the app origin;
  - SMTP is configured for production pilot;
  - `DOCPILOT_LANGGRAPH_CHECKPOINTER=postgres`;
  - a provider key is present under approved environment names;
  - no production variable points at localhost unless explicitly allowed for local target.

Acceptance:

- `python scripts/production_readiness.py --target production` fails when app URL is localhost.
- It fails when `DOCPILOT_AUTH_REQUIRED` is not `true`.
- It fails when `DOCPILOT_SECRETS_KEY` is missing or invalid.
- It passes with a complete VPS pilot environment.

### Workflow trial quota

Problem:

- Project count limits exist, but official-provider workflow runs are not backed by a durable usage ledger.
- Public or pilot users could consume platform AI cost unless manually restricted.

Design:

- Add a durable usage model for AI workflow actions.
- Initial unit: official-provider workflow draft run.
- Starter users get 3 successful or started official-provider workflow runs.
- Professional and enterprise users are unlimited for this pilot, but events are still recorded.
- BYOK runs should still be recorded but should not consume official-provider credits.
- Quota must be checked in the backend before enqueueing or starting a paid-provider workflow.

Suggested table:

- `usage_event`
  - `id`
  - `user_id`
  - `org_id`
  - `project_id`
  - `event_type`
  - `provider_source`
  - `units`
  - `execution_run_id`
  - `created_at`
  - `metadata_json`

Initial event types:

- `workflow_draft_started`
- `workflow_draft_succeeded`
- `workflow_draft_failed`
- `assistant_message_started`

Initial provider sources:

- `official`
- `byok`
- `stub`

Quota policy:

- count `workflow_draft_started` with `provider_source=official`;
- starter limit: 3;
- admin can manually upgrade plan to professional for pilot accounts;
- assistant chat can remain free, but should be rate-limited separately.

Acceptance:

- A starter user can start 3 official-provider draft runs.
- The 4th official-provider draft run returns a clear 403/429-style product error before provider call.
- Professional users can start draft runs without the starter limit.
- BYOK runs are recorded but do not reduce official trial quota.
- Tests cover quota allow, quota deny, plan bypass, and BYOK bypass.

### Auth and access hardening

Problem:

- The dev fallback user is acceptable locally but dangerous in public environments.
- Some access paths need a targeted security audit before pilot.

Design:

- Keep `require_auth` behavior for local development.
- Strengthen readiness checks so pilot/prod cannot run with auth fallback.
- Add focused tests for protected routes that must reject missing tokens when auth is required.
- Audit project-scoped read/write routes for `org_id` or user ownership enforcement.
- Record any remaining access-control gaps in known limitations before pilot.

Acceptance:

- With `DOCPILOT_AUTH_REQUIRED=true`, protected routes reject unauthenticated requests.
- Admin-only routes reject non-admin users.
- Project list/create/detail routes do not cross organization boundaries.

### Email productionization

Problem:

- SMTP adapter exists, but links and templates are still early-stage.
- Email sending is synchronous.

Design:

- For pilot, keep synchronous SMTP sending to avoid adding infrastructure.
- Fix all user-facing links to derive from `DOCPILOT_APP_URL`.
- Make SMTP completeness part of production readiness.
- Keep console fallback only for local/test.

Acceptance:

- Verification, password reset, invitation, and review notification emails contain deployed app links.
- Production readiness fails if SMTP host/user/from are missing for production target.
- Tests assert generated links use configured `DOCPILOT_APP_URL`.

### Billing safety for pilot

Problem:

- Stripe is scaffolded but not ready for public paid self-serve.

Design:

- Keep billing route disabled unless Stripe config is complete.
- For VPS pilot, do not advertise paid checkout as the primary flow.
- Configure pricing page copy to frame pilot/free evaluation honestly.
- Make checkout URLs configurable even if real payment remains disabled.

Acceptance:

- If Stripe is not configured, checkout returns a clear 501.
- If configured, success and cancel URLs use `DOCPILOT_APP_URL`.
- Pricing page does not imply a live paid commercial agreement unless enabled.

### Deployment packaging

Problem:

- `compose.yml` currently starts only PostgreSQL, Redis, and MinIO.
- API, worker, and web need a repeatable pilot deployment path.

Design:

Choose the smallest reliable pilot path:

- Option A: Extend Compose with API, worker, and web services.
- Option B: Keep infrastructure in Compose and run API/worker/web as 1Panel-managed processes/sites.

Recommendation:

- Use Option A for repeatability unless 1Panel constraints make it awkward.
- Add Dockerfiles only if they stay simple and match current `uv`/`pnpm` workflows.
- Keep secrets in an uncommitted `.env.production` or 1Panel environment configuration.

Required services:

- `postgres`;
- `redis`;
- `minio`;
- `api`;
- `worker`;
- `web` or static site artifact.

Acceptance:

- A clean VPS can start all runtime services from documented commands.
- Services restart after VPS reboot.
- API and worker share the same environment contract.
- Web build points at the public API URL.

### Backup and restore

Problem:

- Backup scripts and restore docs exist, but need to be validated against the actual VPS pilot shape.

Design:

- Use existing `scripts/backup.py` and `scripts/restore_drill.py` where possible.
- Document backup location, retention, and manual restore steps.
- Include object storage backup expectations.

Acceptance:

- Operator can take a database backup from VPS.
- Operator can run a restore drill in a non-production database.
- Backup result is recorded in the release notes or pilot runbook.

### Observability and operations

Problem:

- Structured logs and health endpoints exist, but pilot needs a minimal operator view.

Design:

- Require health checks for API, worker, database, Redis, and MinIO.
- Add a simple deployed smoke script or extend release rehearsal to hit public URLs.
- Keep full dashboards as future commercial work unless already cheap to enable.

Acceptance:

- `GET /health` passes through public API.
- Admin detailed health route passes with a valid admin token.
- Worker availability is visible in detailed health or release rehearsal.
- Smoke validates login, project creation, and one non-costing read path.

## Required documentation changes

Update:

- `docs/ops/deployment-and-runbook.md`;
- `docs/ops/staging-deployment.md`;
- `docs/ops/release-checklist.md`;
- `docs/development/configuration-and-secrets.md`;
- `docs/product/known-limitations.md`;
- `services/api/.env.example`;
- add a VPS pilot runbook if the deployment steps are too long for the general runbook.

Documentation must distinguish:

- local;
- VPS pilot;
- future production.

## Security requirements

- No API keys in frontend code, frontend environment, logs, screenshots, or docs.
- Official provider key must be injected server-side only.
- `DOCPILOT_SECRETS_KEY` must be a valid Fernet key in API and worker environments.
- Production JWT secret must be 32+ characters and not equal to the development default.
- `DOCPILOT_AUTH_REQUIRED=true` is mandatory for VPS pilot.
- CORS must allow only the deployed web origin and local origins for local mode.
- Aliyun API key IP allowlist must not include `0.0.0.0/0` or `::/0`.
- MinIO console should not be exposed publicly unless protected by 1Panel/firewall.
- Database and Redis ports should not be publicly exposed beyond the VPS private/runtime boundary.

## Testing strategy

Backend tests:

- production readiness validation;
- URL generation for email and billing;
- auth-required protected route behavior;
- workflow trial quota enforcement;
- BYOK quota bypass;
- subscription plan bypass.

Frontend tests:

- pricing copy for pilot state if changed;
- quota error display when workflow generation is blocked;
- provider settings still masks keys;
- auth flows still route correctly after URL changes.

Worker tests:

- official provider source detection;
- quota check happens before workflow enqueue or paid provider call;
- postgres checkpointer remains production default.

Smoke tests:

- local release rehearsal still passes;
- public VPS smoke checks health and web/API reachability;
- deployed E2E manually verifies create project -> draft -> review -> export.

## Acceptance criteria

The VPS pilot productionization phase is complete when all of the following are true:

1. The app is reachable through HTTPS on the chosen web domain.
2. The API is reachable through HTTPS on `api.bidpilot.rglens.com`.
3. `DOCPILOT_AUTH_REQUIRED=true` is enabled and unauthenticated protected routes are rejected.
4. Email verification and password reset links point to the deployed app domain.
5. A first admin account is provisioned through the bootstrap script.
6. A starter user can run up to 3 official-provider workflow draft runs.
7. A starter user's 4th official-provider workflow draft run is blocked before provider invocation.
8. A professional/admin pilot account can run the same workflow without the starter quota.
9. A complete BidPilot E2E flow succeeds on the VPS: create project, upload, parse, draft, review, export.
10. A database backup is created and a restore drill is completed or explicitly recorded as waived.
11. `python scripts/production_readiness.py --target production` passes with the VPS pilot environment.
12. Known limitations are updated before any external pilot user is onboarded.

## Rollout plan

### Milestone 1: Production configuration cleanup

- Replace hardcoded localhost URLs.
- Add CORS origin configuration.
- Extend readiness checks.
- Update env examples and docs.

### Milestone 2: Trial quota and usage ledger

- Add usage model and migration.
- Enforce workflow trial quota.
- Add tests and user-facing quota errors.

### Milestone 3: Deployment packaging

- Decide Compose-only vs 1Panel mixed deployment.
- Add minimal runtime packaging.
- Document exact VPS startup and restart steps.

### Milestone 4: VPS deployment rehearsal

- Configure secrets.
- Run migrations.
- Bootstrap admin.
- Verify HTTPS web and API.
- Run smoke checks.

### Milestone 5: Pilot E2E acceptance

- Run one full BidPilot scenario.
- Verify email.
- Verify quota.
- Verify backup.
- Update known limitations and pilot notes.

## Risks

### Risk: deployment work expands into full platform ops

Mitigation:

- keep the pilot single-node;
- avoid Kubernetes;
- use the simplest repeatable deployment path.

### Risk: quota enforcement is added only in UI

Mitigation:

- enforce quota in backend before workflow enqueue/provider call;
- test direct API calls.

### Risk: official provider key is exposed or overused

Mitigation:

- official keys stay server-side;
- use Aliyun IP allowlist;
- enforce usage ledger;
- avoid logging provider request headers.

### Risk: existing pilot checklist is too optimistic

Mitigation:

- treat this spec as the stricter VPS pilot gate;
- update old checklist after implementation.

### Risk: real document quality is lower than demo output

Mitigation:

- use a realistic sample bundle for acceptance;
- keep public claims conservative;
- require evidence or missing-evidence markers in generated output.

## Deferred to paid public launch

- Stripe production billing portal;
- detailed invoice and receipt handling;
- failed-payment and cancellation lifecycle;
- mature cost dashboard;
- Redis-backed global abuse controls beyond the pilot quota;
- enterprise SSO/MFA;
- full customer data deletion automation;
- public SLA and support contract.

## Next step

After owner review, create the implementation plan:

`docs/superpowers/plans/2026-06-15-docpilot-vps-pilot-productionization.md`

The plan should break this spec into small, testable tasks with exact files, tests, commands, and checkpoints.
