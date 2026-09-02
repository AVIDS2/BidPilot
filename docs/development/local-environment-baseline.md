# Local Environment Baseline

## Goal

Define the exact local development environment and service assumptions for `DocPilot`.

This document exists so implementation agents do not guess local runtime details or invent parallel infrastructure.

## Mandatory local assumptions

- shell: `powershell`
- Python environment: `conda activate llm`
- web and API: run as direct Node/Python processes
- Docker is not used on the developer machine for this project. VPS production
  retains the versioned Compose topology.
- PostgreSQL, Redis and MinIO may only be used locally when already provisioned
  as host services or through an approved isolated development environment; do
  not start the repository Compose stack locally.

## Verified direct-process profile (2026-09-01)

The current Windows development profile intentionally does not use Docker or a
public API. It is the profile used for frontend and API contract acceptance in
the `codex/kiranism-bidpilot` worktree:

- Next web: `http://127.0.0.1:3300`
- FastAPI: `http://127.0.0.1:8000`
- Pi sidecar: `http://127.0.0.1:8787`
- isolated SQLite file: `.tmp/bidpilot-local.sqlite3`
- `DOCPILOT_LOCAL_DIRECT_ASSISTANT=true` (uses the same Pi executor without a
  broker when Redis/Worker are unavailable)
- Redis, MinIO and Celery Worker: not started in this profile

The SQLite profile is suitable for local auth, project/workspace pages, radar,
readiness presentation and REST contract checks. It is not a replacement for
PostgreSQL/pgvector or a Worker integration environment; upload/indexing,
queued workflow execution and object-storage flows must remain explicitly
marked unavailable until approved local Redis/MinIO instances are provisioned.
The browser must never use `https://bidpilot-api.rglens.com` during this profile.
The Next BFF uses the loopback API and derives the cookie `Secure` flag from
the actual request or forwarded protocol. This keeps `next start` over local
HTTP usable while retaining secure cookies behind the HTTPS production proxy.

## Python environment

Before Python work:

```powershell
conda activate llm
```

All API and worker Python commands should assume this environment unless the repository later documents a replacement.

## PostgreSQL baseline

The historical local Docker baseline is retained below for reference only. It
must not be started on the developer machine. Local API integration tests need
an already provisioned isolated PostgreSQL instance whose database name ends in
`_test`.

Current compose file:

- `compose.yml`

Current service:

- production container name: `bidpilot-postgres`
- image: `pgvector/pgvector:pg17`

Connection baseline when an isolated host/dev instance is available:

- host: `localhost`
- host port: `5433`
- database: `docpilot`
- dedicated test database: `docpilot_test`
- username: `docpilot`
- password: `docpilot`

Connection string:

```text
postgresql://docpilot:docpilot@localhost:5433/docpilot
```

## PostgreSQL rule

- do not use a production database for local development or tests
- do not create a second unrelated Postgres setup outside this project unless the docs are updated
- if an isolated local Postgres instance is not available, run UI-only checks and report the backend limitation

## Test database rule

API tests and local release rehearsals must never use `docpilot`. They require a
dedicated database whose name ends in `_test`. Prepare the documented local test
database once:

```powershell
uv run --directory services/api python ../../scripts/prepare_local_test_database.py
```

Then set `DOCPILOT_TEST_DATABASE_URL` in an ignored local environment file to
the same local PostgreSQL connection with database name `docpilot_test`, and
initialize it before testing:

```powershell
$env:DOCPILOT_DATABASE_URL = $env:DOCPILOT_TEST_DATABASE_URL
uv run --directory services/api alembic upgrade head
uv run --directory services/api python ../../scripts/verify_migration_health.py
```

The test bootstrap rejects a database name that does not end in `_test` before
it imports application code. This protects local development data and makes
release-rehearsal evidence reproducible.

`alembic` is invoked outside the test bootstrap, so it reads
`DOCPILOT_DATABASE_URL` directly. Set it explicitly as shown above; do not run
migrations against `docpilot` while intending to migrate `docpilot_test`.

`verify_migration_health.py` also creates one randomly named local scratch
database ending in `_test`, upgrades it from empty state, checks all ORM model
tables, and removes only that scratch database when the check finishes. It
refuses remote hosts and names outside its generated scratch namespace. Use
`--keep-scratch` only when manually investigating a migration failure.

Historical Compose start command (VPS only; do not run locally):

```powershell
docker compose up -d postgres
```

## Reserved local ports

These are the default local development ports to use unless the docs are updated:

- web: `3300` (the historical Vite port `5173` is retired for this Next app)
- api: `8000`
- Pi sidecar: `8787`
- postgres: `5433` when an approved host PostgreSQL instance exists
- redis: `6379`
- minio api: `9000`
- minio console: `9001`

If a service is not implemented yet, keep the port reserved anyway so future setup stays consistent.

## Model provider baseline

Current provider families:

- Aliyun DashScope / Model Studio
- OpenRouter embeddings

Official OpenAI-compatible base URL for the Beijing region:

```text
https://dashscope.aliyuncs.com/compatible-mode/v1
```

OpenRouter embeddings endpoint:

```text
https://openrouter.ai/api/v1/embeddings
```

Current API key for this local development context:

```text
<your-api-key>
```

Preferred model baseline:

- workflow LLM model: `qwen3.5-flash`
- official text embedding model: `qwen/qwen3-embedding-8b`
- embedding output dimensions: `1536` to match the current `knowledge_chunk.embedding VECTOR(1536)` schema

If a different model is needed, check the provider's official documentation first and use the most suitable current model instead of guessing. Do not mix embeddings with different dimensions in the same pgvector column.

## Recommended environment variables

For local development, use these values:

```text
DOCPILOT_ENV=local
DOCPILOT_LOG_LEVEL=INFO
DOCPILOT_APP_URL=http://127.0.0.1:3300

DOCPILOT_DATABASE_URL=postgresql://docpilot:docpilot@localhost:5433/docpilot
DOCPILOT_REDIS_URL=redis://localhost:6379/0

DOCPILOT_PROVIDER_DOMESTIC_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DOCPILOT_PROVIDER_DOMESTIC_API_KEY=<your-api-key>
DOCPILOT_LLM_MODEL_PRIMARY=qwen3.5-flash
OPENROUTER_API_KEY=<your-openrouter-api-key>
OPENROUTER_EMBEDDING_MODEL=qwen/qwen3-embedding-8b
OPENROUTER_EMBEDDING_DIMENSIONS=1536
DOCPILOT_SECRETS_KEY=<generated-fernet-key>
```

Optional compatibility alias if a library expects DashScope naming:

```text
ALIYUN_API_KEY=<your-aliyun-bailian-api-key>
DASHSCOPE_API_KEY=<your-dashscope-api-key>
```

Generate `DOCPILOT_SECRETS_KEY` locally with:

```bash
uv run --directory services/api python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

This key protects user-supplied provider API keys stored in `provider_config`. Keep it out of Git, logs, screenshots, and chat transcripts.

LangGraph checkpoint mode:

```text
DOCPILOT_LANGGRAPH_CHECKPOINTER=postgres
```

Use `DOCPILOT_LANGGRAPH_CHECKPOINTER=memory` only for local workflow smoke tests when isolating Postgres checkpoint behavior. Do not use memory checkpoints for staging or production.

The direct-process profile intentionally has no Redis, MinIO or Celery Worker.
Use `/health` for local API liveness and the Pi sidecar `/health` for the
assistant process. `/health/ready` checks the complete dependency set and may
return degraded or wait on unavailable optional services in this profile; a
passing readiness result requires an approved PostgreSQL/Redis/MinIO/Worker
environment and must not be inferred from the SQLite browser profile.

## Local startup order

Before meaningful development:

1. `conda activate llm` when Python work is required.
2. For frontend/API contract work, initialize the ignored SQLite profile and
   start FastAPI, Pi and Next directly on the loopback ports above.
3. For PostgreSQL/queue/object-storage work, first confirm that approved host
   services are running; never start the repository Compose stack locally.
4. Use only the loopback `DOCPILOT_API_URL` for the local Next process.
5. Run tests only against a dedicated local database ending in `_test`.

## Future rule

If the local environment changes, update this document, `configuration-and-secrets.md`, and any affected runbook or compose docs in the same change.
