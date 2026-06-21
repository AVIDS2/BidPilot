# VPS Pilot Deployment

## Goal

Bring DocPilot up on the VPS as a controlled pilot with public HTTPS web/API domains, auth enforced, SMTP enabled, and a repeatable launch/rollback path.

## Topology

- web: static Vite build served by Nginx
- api: FastAPI
- worker: Celery
- postgres: pgvector
- redis: queue/cache
- minio: object storage

## Required environment

Use a managed secret source or an uncommitted `.env.production` file on the VPS.

Required values:

- `DOCPILOT_DATABASE_URL`
- `DOCPILOT_REDIS_URL`
- `DOCPILOT_MINIO_ENDPOINT`
- `DOCPILOT_MINIO_ACCESS_KEY`
- `DOCPILOT_MINIO_SECRET_KEY`
- `DOCPILOT_JWT_SECRET`
- `DOCPILOT_SECRETS_KEY`
- `DOCPILOT_AUTH_REQUIRED=true`
- `DOCPILOT_APP_URL=https://bidpilot.rglens.com`
- `DOCPILOT_CORS_ORIGINS=https://bidpilot.rglens.com`
- `DOCPILOT_LANGGRAPH_CHECKPOINTER=postgres`
- `DOCPILOT_SMTP_HOST`
- `DOCPILOT_SMTP_USER`
- `DOCPILOT_SMTP_FROM`
- one provider key, such as `DOCPILOT_PROVIDER_DOMESTIC_API_KEY`
- `DOCPILOT_TURNSTILE_SECRET_KEY`
- `VITE_TURNSTILE_SITE_KEY`

## Build and start

From the repository root:

```powershell
docker compose up -d --build
```

This starts the full pilot stack and keeps the infrastructure containers in place for the worker and API.

## Database migrations

Run after the API container is available:

```powershell
docker compose exec api uv run alembic upgrade head
```

## First admin bootstrap

```powershell
$env:DOCPILOT_BOOTSTRAP_ADMIN_PASSWORD = "<strong-random-password>"
docker compose exec api python scripts/bootstrap_admin.py --email pilot-admin@example.com --display-name "Pilot Admin"
```

## Access

- web: `https://bidpilot.rglens.com`
- api: `https://api.bidpilot.rglens.com`

The reverse proxy should route public traffic to the web and API containers. Keep database, Redis, and MinIO internal.

## Health checks

- API: `GET /health`
- production readiness: `python scripts/production_readiness.py --target production`

## Backup and restore

Before opening the pilot to users:

```powershell
docker compose exec api python scripts/backup.py backup
```

Then run the restore drill in the designated non-production database before promotion.

## Rollback

- web can roll back independently;
- API and worker roll back together;
- database changes require backup + restore, not blind down-migrations.
