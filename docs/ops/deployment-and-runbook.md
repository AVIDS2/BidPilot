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

## Migration policy

- schema changes are applied through Alembic
- destructive migrations require backup confirmation
- application code must support a short rolling window when possible

## Backup policy

- database logical backups daily
- object storage versioning enabled
- weekly restore verification in staging
- recovery targets should stay aligned with `docs/product/non-functional-requirements.md`

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
