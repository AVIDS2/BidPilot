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

Required secret-backed values:

- `DOCPILOT_DATABASE_URL`
- `DOCPILOT_REDIS_URL`
- `DOCPILOT_MINIO_ENDPOINT`
- `DOCPILOT_MINIO_ACCESS_KEY`
- `DOCPILOT_MINIO_SECRET_KEY`
- `DOCPILOT_JWT_SECRET`
- one workflow LLM provider API key such as `DOCPILOT_PROVIDER_DOMESTIC_API_KEY`, `DOCPILOT_PROVIDER_OPENAI_API_KEY`, `OPENAI_API_KEY`, or `LLM_API_KEY`
- `OPENROUTER_API_KEY` for official embeddings, with `OPENROUTER_EMBEDDING_MODEL=qwen/qwen3-embedding-8b` and `OPENROUTER_EMBEDDING_DIMENSIONS=1536`
- `DOCPILOT_LANGGRAPH_CHECKPOINTER=postgres`

`DOCPILOT_AUTH_REQUIRED` must be `true`.

For Aliyun Bailian/DashScope, configure API key IP allowlists to the staging/production egress IPs before enabling official-provider workflow trials. Remove wildcard allowlist entries such as `0.0.0.0/0` and `::/0`.

## Migration policy

- schema changes are applied through Alembic
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
