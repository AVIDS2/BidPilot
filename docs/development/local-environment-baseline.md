# Local Environment Baseline

## Goal

Define the exact local development environment and service assumptions for `DocPilot`.

This document exists so implementation agents do not guess local runtime details or invent parallel infrastructure.

## Mandatory local assumptions

- shell: `powershell`
- Python environment: `conda activate llm`
- PostgreSQL: use the project-local Docker service, not any host-installed PostgreSQL
- if a required local service is missing, create it inside this repository's Docker setup rather than using unrelated local state

## Python environment

Before Python work:

```powershell
conda activate llm
```

All API and worker Python commands should assume this environment unless the repository later documents a replacement.

## PostgreSQL baseline

PostgreSQL is provided by Docker in this project.

Current compose file:

- `compose.yml`

Current service:

- container name: `docpilot-postgres`
- image: `pgvector/pgvector:pg17`

Connection baseline:

- host: `localhost`
- host port: `5433`
- database: `docpilot`
- username: `docpilot`
- password: `docpilot`

Connection string:

```text
postgresql://docpilot:docpilot@localhost:5433/docpilot
```

## PostgreSQL rule

- do not use a host-installed PostgreSQL instance for DocPilot
- do not create a second unrelated Postgres setup outside this project unless the docs are updated
- if Postgres is needed and not running, start it from this repository's Docker setup

Start command:

```powershell
docker compose up -d postgres
```

## Reserved local ports

These are the default local development ports to use unless the docs are updated:

- web: `5173`
- api: `8000`
- postgres: `5433`
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
DOCPILOT_APP_URL=http://localhost:5173

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

## Local startup order

Before meaningful development:

1. `conda activate llm`
2. start Docker services required for the current task
3. confirm Postgres is running on `localhost:5433`
4. use the documented API base URL and models for provider setup
5. only then start app services and run tests

## Future rule

If the local environment changes, update this document, `configuration-and-secrets.md`, and any affected runbook or compose docs in the same change.
