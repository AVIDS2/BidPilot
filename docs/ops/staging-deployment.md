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
| `DEEPSEEK_API_KEY` | _(none)_ | Preferred platform drafting/assistant key; stays server-side |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | DeepSeek Chat Completions base URL |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | DeepSeek Chat Completions model; platform default when unset |
| `OPENCODE_API_KEY` | _(none)_ | OpenCode Go platform key; when configured it is the preferred official Chat Completions provider |
| `OPENCODE_BASE_URL` | `https://opencode.ai/zen/go/v1` | OpenCode Go OpenAI-compatible base URL |
| `OPENCODE_MODEL` | `deepseek-v4-flash` | OpenCode Go model name |
| `LLM_API_KEY` / `OPENAI_API_KEY` | _(none)_ | Legacy or custom workflow LLM key |
| `LLM_API_URL` | `https://api.openai.com/v1/chat/completions` | Legacy/custom LLM endpoint |
| `LLM_MODEL` | `gpt-4o-mini` | Legacy/custom LLM model name |
| `OPENROUTER_API_KEY` | _(none)_ | Official OpenRouter key for embeddings |
| `OPENROUTER_EMBEDDING_MODEL` | `qwen/qwen3-embedding-8b` | OpenRouter embedding model name |
| `OPENROUTER_EMBEDDING_DIMENSIONS` | `1536` | Embedding output dimensions; must match `knowledge_chunk.embedding VECTOR(1536)` |
| `DOCPILOT_OCR_ENABLED` | `true` | Enable local Worker OCR fallback for sparse-text PDF pages |
| `DOCPILOT_OCR_LANGS` | `chi_sim+eng` | Installed Tesseract languages; no cloud OCR fallback is used |
| `EMBEDDING_API_KEY` / `OPENAI_API_KEY` | _(none)_ | Legacy embedding API key fallback |
| `EMBEDDING_API_URL` | `https://api.openai.com/v1/embeddings` | Legacy embedding endpoint |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Legacy embedding model name |

For the controlled VPS pilot deployment shape, see `docs/ops/vps-pilot-deployment.md` instead of this local/staging guide.

## Production Checklist

- [ ] Set `DOCPILOT_JWT_SECRET` to a cryptographically random 32+ byte string
- [ ] Set `DOCPILOT_AUTH_REQUIRED=true`
- [ ] Configure `DEEPSEEK_API_KEY` (or an explicit compatible workflow provider) and `OPENROUTER_API_KEY` for embeddings
- [ ] Use managed Postgres with pgvector extension
- [ ] Use managed Redis (ElastiCache, etc.)
- [ ] Use managed object storage (S3 with MinIO gateway or direct S3)
- [ ] Enable TLS on API and frontend
- [ ] Set up Celery worker with concurrency and health checks
- [ ] Configure backup for PostgreSQL
