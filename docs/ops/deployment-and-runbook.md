# Deployment and Runbook

## Environment model

### Local

Purpose:

- daily development
- parser and workflow debugging
- UI iteration

Stack:

- web
- api
- worker
- worker-beat (scheduled retention and maintenance tasks)
- postgres
- redis
- minio

### Staging

Purpose:

- release validation
- integration testing
- performance smoke testing

Requirements:

- isolated storage
- seeded test data
- telemetry enabled

### Production

Purpose:

- durable business use

Requirements:

- managed or hardened PostgreSQL
- encrypted object storage
- backup and restore validation
- secrets management
- alerting

## Release flow

1. merge to main
2. run CI
3. build tagged images
4. deploy to staging
5. run smoke and migration checks
6. promote to production

The VPS `deploy.sh` uses the repository's versioned
`docker-compose.production.yml` as the source for `/app/bidpilot/docker-compose.yml`.
It writes a temporary sibling file, validates it with the existing server `.env`,
then atomically replaces the outer Compose file before rebuilding containers.
This prevents application code and production topology from silently diverging;
the outer `.env` is never copied, committed, or changed by the script.

The production script builds application images sequentially because the pilot
VPS has limited memory and no swap. It keeps PostgreSQL, Redis, and MinIO up,
stops only the application containers while building, and restores them if a
build fails. Local development must use direct Node/Python processes; Docker is
reserved for this VPS production topology.

Pi releases are fail-closed: when `DOCPILOT_ASSISTANT_ENGINE=pi`, deployment
must use the complete production Compose topology, including the healthy
`pi-agent` sidecar. A missing `DOCPILOT_PI_INTERNAL_SECRET` or an invalid
production Compose file stops deployment before application services are
replaced. The legacy application-only compatibility path is available only to
an explicitly non-Pi deployment; it must never produce a new API that depends
on a sidecar absent from the live topology.

For an existing pilot that still has the older deploy script, update that script
once from the reviewed repository version before using the new release path.

Run the local release-candidate rehearsal before staging promotion:

```powershell
python scripts/release_rehearsal.py --run
```

See `docs/ops/release-rehearsal-runbook.md` for optional browser, load, and production-readiness gates.

## Production readiness gate

Before promotion, inject production-equivalent secrets and run:

```powershell
python scripts/production_readiness.py --target production
```

The checker validates that required deployment variables are present, auth is enforced, localhost endpoints are not used, and known development defaults are not promoted.
The production Compose deployment runs the same check as a one-shot `readiness`
service before migrations; a failed gate blocks API and Worker startup.

Required secret-backed values:

- `DOCPILOT_DATABASE_URL`
- `DOCPILOT_POSTGRES_DB`
- `DOCPILOT_POSTGRES_USER`
- `DOCPILOT_POSTGRES_PASSWORD`
- `DOCPILOT_REDIS_URL`
- `DOCPILOT_REDIS_PASSWORD`
- `DOCPILOT_MINIO_ENDPOINT`
- `DOCPILOT_MINIO_ACCESS_KEY`
- `DOCPILOT_MINIO_SECRET_KEY`
- `DOCPILOT_JWT_SECRET`
- one transactional email provider:
  `RESEND_API_KEY` (preferred) with optional `DOCPILOT_RESEND_FROM`, or the
  complete SMTP set `DOCPILOT_SMTP_HOST`, `DOCPILOT_SMTP_USER`,
  `DOCPILOT_SMTP_PASS`, and `DOCPILOT_SMTP_FROM`
- one workflow LLM provider API key. The current production profile is MiMo
  direct balance through `DOCPILOT_ASSISTANT_API_KEY`, with
  `DOCPILOT_ASSISTANT_PROVIDER_ID=mimo`, base URL
  `https://api.xiaomimimo.com/v1`, and model `mimo-v2.5-pro`. The compatibility
  aliases `MIMO_API_KEY` / `XIAOMI_API_KEY`, `DEEPSEEK_API_KEY`,
  `OPENCODE_API_KEY`, `DOCPILOT_PROVIDER_DOMESTIC_API_KEY`,
  `DOCPILOT_PROVIDER_OPENAI_API_KEY`, `OPENAI_API_KEY`, and `LLM_API_KEY`
  remain supported. Set one platform profile, not conflicting values from
  several providers.
- `OPENROUTER_API_KEY` for official embeddings, with `OPENROUTER_EMBEDDING_MODEL=qwen/qwen3-embedding-8b` and `OPENROUTER_EMBEDDING_DIMENSIONS=1536`
- `DOCPILOT_ENV=production`
- `DOCPILOT_LANGGRAPH_CHECKPOINTER=postgres`
- `DOCPILOT_AGENT_CHECKPOINTER=postgres`
- `DOCPILOT_ASSISTANT_ENGINE=pi`
- `DOCPILOT_PI_AGENT_URL=http://pi-agent:8787`
- `DOCPILOT_PI_TOOL_BRIDGE_URL=http://api:8000/internal/pi/tools/execute`
- `DOCPILOT_PI_INTERNAL_SECRET` shared only by the API, Pi sidecar, and Worker
  queue consumer; it authorizes short-lived run-scoped bridge/task tokens and
  must never be exposed to the browser

`DOCPILOT_AUTH_REQUIRED` must be `true`.

The production Compose file intentionally has no hard-coded PostgreSQL or
MinIO root credentials. Its PostgreSQL service reads the three
`DOCPILOT_POSTGRES_*` values, and its MinIO service reuses
`DOCPILOT_MINIO_ACCESS_KEY` and `DOCPILOT_MINIO_SECRET_KEY` from the untracked
server `.env`. The database URL must use the same credentials with a
URL-encoded password.

For an existing VPS volume, do not simply change these values and restart:
PostgreSQL and MinIO preserve identities inside their data volumes. Plan a
maintenance window, rotate the database role and object-storage credentials
through their respective administration interfaces, update the server `.env`,
then run the readiness gate before bringing the stack back up. A deployment
that still uses repository defaults is intentionally blocked.

Redis is private to Docker and loopback-bound for diagnostics, but production
still requires `DOCPILOT_REDIS_PASSWORD`. Set the same value in the Redis URL
as a URL-encoded password, for example
`redis://:encoded-password@redis:6379/0`; Compose passes the unencoded value to
Redis at runtime and waits for an authenticated `PONG` before starting API or
Worker services.

For Aliyun Bailian/DashScope, configure API key IP allowlists to the staging/production egress IPs before enabling official-provider workflow trials. Remove wildcard allowlist entries such as `0.0.0.0/0` and `::/0`.

## Migration policy

- schema changes are applied through Alembic
- production Compose runs the `readiness` gate, then the `migrate` one-shot service before API or Worker starts
- the `checkpoints` one-shot service runs only after migration succeeds and prepares LangGraph checkpoint tables
- a failed migration or checkpoint setup blocks API and Worker startup; do not bypass it with manual application restarts
- destructive migrations require backup confirmation
- application code must support a short rolling window when possible

## Backup policy

- database logical backups daily
- object storage versioning enabled
- weekly restore verification in staging
- recovery targets should stay aligned with `docs/product/non-functional-requirements.md`
- staging restore drills should follow `docs/ops/backup-restore-drill.md`

## Incident priorities

### P1

- data corruption risk
- export failures for approved deliverables
- auth bypass

### P2

- parsing backlog saturation
- section drafting unavailable
- review actions failing

### P3

- degraded dashboards
- delayed non-critical jobs

## First-response runbook

1. confirm blast radius
2. identify affected project IDs and services
3. freeze risky write paths if needed
4. inspect traces and recent deployment history
5. decide rollback or hotfix path
6. record incident summary in audit trail

## Rollback rules

- frontend can roll back independently
- API and worker roll back together when schema expectations change
- database rollbacks require restore plans, not blind down migrations

For the VPS pilot deployment path, use `docs/ops/vps-pilot-deployment.md`.
