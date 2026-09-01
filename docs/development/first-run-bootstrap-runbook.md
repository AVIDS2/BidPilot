# First Run Bootstrap Runbook

## Goal

Provide one explicit first-day startup runbook for implementation agents.

Use this before writing or deleting meaningful code in a fresh or partially initialized repository state.

## Non-negotiable safety rules

- do not delete files or infrastructure because the environment is not yet working
- do not replace the documented stack with a new one because one dependency is missing
- do not start Docker or create a second unrelated local database for this
  project; use the verified direct-process profile when host dependencies are
  unavailable
- do not switch away from `conda activate llm` unless the docs are updated first

## First-run sequence

### 1. Enter the documented Python environment

```powershell
conda activate llm
```

### 2. Check the direct-process profile

```powershell
Test-NetConnection 127.0.0.1 -Port 8000
Test-NetConnection 127.0.0.1 -Port 8787
```

For UI/API work, the expected local API and Pi processes are direct Windows
processes. Docker is not part of the developer workflow.

### 3. Prepare the local contract database

```powershell
uv run --directory services/api python -c "from contracts.db import Base; import app.models; from app.db import engine; Base.metadata.create_all(engine)"
```

Use the ignored local SQLite URL from the baseline when PostgreSQL is not
available. Do not point the web app at the production API for convenience.

### 4. Verify the local web/API boundary

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8787/health
```

Expected:

- both loopback services return HTTP 200

### 5. Verify the documented connection target

```powershell
Test-NetConnection 127.0.0.1 -Port 3300
```

Expected:

- the Next app is reachable on port `3300`

### 6. Confirm local provider baseline

Use:

- base URL: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- API key: `<your-api-key>`
- primary model: `qwen3.5-flash`
- multimodal embedding: `qwen3-vl-embedding`

When creating an Aliyun Bailian/DashScope API key, remove the default `0.0.0.0/0` and `::/0` whitelist entries before saving the key. Allow only known server egress IPs. Do not use a key with a public wildcard whitelist for local demos or production.
- text embedding: `text-embedding-v4`

### 7. Only after environment confirmation, start implementation

Read:

1. `docs/development/local-environment-baseline.md`
2. `docs/development/current-execution-state.md`
3. `docs/development/agent-execution-manual.md`
4. `docs/README.md`

Then continue with the active phase plan.

## If something is missing

### If PostgreSQL, Redis or MinIO is not running

- continue with the direct-process SQLite/API/Pi profile for UI and REST work
- report asynchronous and object-storage flows as unavailable
- do not start Docker or point local UI traffic at the public API

### If the app services do not exist yet

- create them according to the active phase plan
- do not conclude the stack is wrong just because the code is not scaffolded yet

### If a dependency is not installed

- install the missing dependency inside the documented stack
- do not swap frameworks or runtimes as a workaround

## Completion condition

The first-run bootstrap is complete only when:

- `conda activate llm` is active
- Docker is available
- `docpilot-postgres` is running on `5433`
- provider baseline is known
- the current phase entry docs have been read
