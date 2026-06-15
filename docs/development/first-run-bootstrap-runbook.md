# First Run Bootstrap Runbook

## Goal

Provide one explicit first-day startup runbook for implementation agents.

Use this before writing or deleting meaningful code in a fresh or partially initialized repository state.

## Non-negotiable safety rules

- do not delete files or infrastructure because the environment is not yet working
- do not replace the documented stack with a new one because one dependency is missing
- do not create a second local PostgreSQL outside the project Docker setup
- do not switch away from `conda activate llm` unless the docs are updated first

## First-run sequence

### 1. Enter the documented Python environment

```powershell
conda activate llm
```

### 2. Check Docker is available

```powershell
docker version
docker compose version
```

If Docker is unavailable, stop and report the blocker rather than inventing a non-Docker local stack.

### 3. Start the documented PostgreSQL service

```powershell
docker compose up -d postgres
```

### 4. Verify PostgreSQL container health

```powershell
docker ps --filter "name=docpilot-postgres"
```

Expected:

- container name `docpilot-postgres`
- mapped port `5433`
- healthy or running status

### 5. Verify the documented connection target

```powershell
Test-NetConnection localhost -Port 5433
```

Expected:

- port `5433` reachable

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

### If PostgreSQL is not running

- start it with `docker compose up -d postgres`
- do not create a second database elsewhere

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
