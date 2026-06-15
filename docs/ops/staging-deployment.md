# Staging Deployment Guide

## Prerequisites

- Docker + Docker Compose
- Python 3.13+ with `uv`
- Node.js 22+ with `pnpm`

## 1. Start Infrastructure

```bash
docker compose up -d
```

This starts:
- **PostgreSQL** (pgvector) on port 5433 — user: `docpilot`, pass: `docpilot123`, db: `docpilot`
- **Redis** on port 6379
- **MinIO** on port 9000 — user: `docpilot`, pass: `docpilot123`

## 2. Run Database Migrations

```bash
cd services/api
uv run alembic upgrade head
```

## 3. Start API Server

```bash
cd services/api
DOCPILOT_DATABASE_URL=postgresql://docpilot:docpilot123@localhost:5433/docpilot \
DOCPILOT_REDIS_URL=redis://localhost:6379/0 \
DOCPILOT_MINIO_ENDPOINT=localhost:9000 \
uv run uvicorn app.main:app --reload --port 8000
```

## 4. Start Celery Worker

```bash
cd services/worker
DOCPILOT_DATABASE_URL=postgresql://docpilot:docpilot123@localhost:5433/docpilot \
DOCPILOT_REDIS_URL=redis://localhost:6379/0 \
DOCPILOT_MINIO_ENDPOINT=localhost:9000 \
uv run celery -A app.celery_app worker --loglevel=info
```

## 5. Start Frontend Dev Server

```bash
cd apps/web
VITE_API_URL=http://localhost:8000 pnpm dev
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DOCPILOT_DATABASE_URL` | `postgresql://docpilot:docpilot123@localhost:5433/docpilot` | Postgres connection string |
| `DOCPILOT_REDIS_URL` | `redis://localhost:6379/0` | Redis URL for Celery broker |
| `DOCPILOT_MINIO_ENDPOINT` | `localhost:9000` | MinIO endpoint |
| `DOCPILOT_MINIO_ACCESS_KEY` | `docpilot` | MinIO access key |
| `DOCPILOT_MINIO_SECRET_KEY` | `docpilot123` | MinIO secret key |
| `DOCPILOT_JWT_SECRET` | `dev-secret-change-in-production-32bytes!` | JWT signing key |
| `DOCPILOT_AUTH_REQUIRED` | `false` | Set `true` to enforce Bearer token auth |
| `LLM_API_KEY` / `OPENAI_API_KEY` | _(none)_ | LLM API key for drafting |
| `LLM_API_URL` | `https://api.openai.com/v1/chat/completions` | LLM endpoint |
| `LLM_MODEL` | `gpt-4o-mini` | LLM model name |
| `EMBEDDING_API_KEY` / `OPENAI_API_KEY` | _(none)_ | Embedding API key |
| `EMBEDDING_API_URL` | `https://api.openai.com/v1/embeddings` | Embedding endpoint |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model name |

For the controlled VPS pilot deployment shape, see `docs/ops/vps-pilot-deployment.md` instead of this local/staging guide.

## Production Checklist

- [ ] Set `DOCPILOT_JWT_SECRET` to a cryptographically random 32+ byte string
- [ ] Set `DOCPILOT_AUTH_REQUIRED=true`
- [ ] Configure `LLM_API_KEY` and `EMBEDDING_API_KEY` (or `OPENAI_API_KEY`)
- [ ] Use managed Postgres with pgvector extension
- [ ] Use managed Redis (ElastiCache, etc.)
- [ ] Use managed object storage (S3 with MinIO gateway or direct S3)
- [ ] Enable TLS on API and frontend
- [ ] Set up Celery worker with concurrency and health checks
- [ ] Configure backup for PostgreSQL
