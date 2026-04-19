# DocPilot Phase 0 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** bootstrap the repository, local runtime, shared contracts, and persistence skeleton so all later DocPilot work lands on stable foundations

**Architecture:** start with a modular split across `apps/web`, `services/api`, `services/worker`, and `packages/contracts`, but deploy locally as one Docker Compose stack. Keep domain truth in PostgreSQL and use Redis plus object storage for queueing and artifacts.

**Tech Stack:** TypeScript, React, Vite, Python, FastAPI, SQLAlchemy 2, PostgreSQL, pgvector, Redis, MinIO, Celery, Docker Compose, OpenTelemetry

---

### Task 1: Bootstrap repository layout and root tooling

**Files:**
- Create: `package.json`
- Create: `pnpm-workspace.yaml`
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `README.md`

- [ ] **Step 1: Write the failing test**

```bash
test -f package.json
test -f pnpm-workspace.yaml
test -f pyproject.toml
test -f .gitignore
test -f README.md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash -lc "test -f package.json && test -f pnpm-workspace.yaml && test -f pyproject.toml && test -f .gitignore && test -f README.md"`
Expected: non-zero exit because the files do not exist yet

- [ ] **Step 3: Write minimal implementation**

```json
{
  "name": "docpilot",
  "private": true,
  "packageManager": "pnpm@10.0.0",
  "scripts": {
    "lint": "pnpm -r lint",
    "test": "pnpm -r test"
  }
}
```

```yaml
packages:
  - apps/*
  - packages/*
```

```toml
[project]
name = "docpilot"
version = "0.1.0"
requires-python = ">=3.12"

[tool.uv.workspace]
members = ["services/api", "services/worker"]
```

```gitignore
node_modules/
.venv/
__pycache__/
.pytest_cache/
dist/
.DS_Store
.env
coverage/
```

```md
# DocPilot

Enterprise AI Document Execution System.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bash -lc "test -f package.json && test -f pnpm-workspace.yaml && test -f pyproject.toml && test -f .gitignore && test -f README.md"`
Expected: PASS with exit code 0

- [ ] **Step 5: Commit**

```bash
git add package.json pnpm-workspace.yaml pyproject.toml .gitignore README.md
git commit -m "chore: bootstrap docpilot root workspace"
```

### Task 2: Create the React workbench shell

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/index.html`
- Create: `apps/web/src/main.tsx`
- Create: `apps/web/src/app.tsx`
- Create: `apps/web/vite.config.ts`
- Create: `apps/web/src/app.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
import { render, screen } from "@testing-library/react";
import { App } from "./app";

test("renders DocPilot shell", () => {
  render(<App />);
  expect(screen.getByText("DocPilot Workbench")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --dir apps/web test -- --runInBand`
Expected: FAIL because the app files do not exist

- [ ] **Step 3: Write minimal implementation**

```json
{
  "name": "@docpilot/web",
  "private": true,
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "test": "vitest"
  },
  "dependencies": {
    "react": "^19.1.1",
    "react-dom": "^19.1.1"
  },
  "devDependencies": {
    "@testing-library/react": "^16.3.0",
    "@types/react": "^19.1.2",
    "@types/react-dom": "^19.1.2",
    "@vitejs/plugin-react": "^4.4.1",
    "typescript": "^5.8.3",
    "vite": "^7.0.0",
    "vitest": "^3.1.0"
  }
}
```

```tsx
export function App() {
  return <main>DocPilot Workbench</main>;
}
```

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./app";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
});
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --dir apps/web test -- --runInBand`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/web
git commit -m "feat: add DocPilot React workbench shell"
```

### Task 3: Create the FastAPI service and database skeleton

**Files:**
- Create: `services/api/pyproject.toml`
- Create: `services/api/app/main.py`
- Create: `services/api/app/db.py`
- Create: `services/api/app/models.py`
- Create: `services/api/tests/test_health.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_healthcheck() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory services/api pytest services/api/tests/test_health.py -v`
Expected: FAIL because the app package does not exist

- [ ] **Step 3: Write minimal implementation**

```toml
[project]
name = "docpilot-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "alembic>=1.15.0",
  "fastapi>=0.115.12",
  "psycopg[binary]>=3.2.0",
  "pydantic>=2.11.0",
  "sqlalchemy>=2.0.39",
  "uvicorn>=0.34.0"
]

[dependency-groups]
dev = [
  "pytest>=8.3.5",
  "httpx>=0.28.1"
]
```

```python
from fastapi import FastAPI

app = FastAPI(title="DocPilot API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


engine = create_engine("postgresql+psycopg://docpilot:docpilot@localhost:5432/docpilot")
```

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Project(Base):
    __tablename__ = "project"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory services/api pytest services/api/tests/test_health.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/api
git commit -m "feat: add FastAPI service skeleton"
```

### Task 4: Add local infrastructure and startup path

**Files:**
- Create: `compose.yml`
- Create: `services/worker/pyproject.toml`
- Create: `services/worker/app/tasks.py`
- Create: `services/worker/tests/test_tasks.py`

- [ ] **Step 1: Write the failing test**

```python
from app.tasks import ping


def test_ping_task() -> None:
    assert ping() == "pong"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory services/worker pytest services/worker/tests/test_tasks.py -v`
Expected: FAIL because the worker package does not exist

- [ ] **Step 3: Write minimal implementation**

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg17
    environment:
      POSTGRES_DB: docpilot
      POSTGRES_USER: docpilot
      POSTGRES_PASSWORD: docpilot
    ports:
      - "5432:5432"
  redis:
    image: redis:7.4-alpine
    ports:
      - "6379:6379"
  minio:
    image: minio/minio:RELEASE.2025-01-20T14-49-07Z
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: docpilot
      MINIO_ROOT_PASSWORD: docpilot123
    ports:
      - "9000:9000"
      - "9001:9001"
```

```toml
[project]
name = "docpilot-worker"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "celery[redis]>=5.5.0"
]

[dependency-groups]
dev = [
  "pytest>=8.3.5"
]
```

```python
def ping() -> str:
    return "pong"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory services/worker pytest services/worker/tests/test_tasks.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add compose.yml services/worker
git commit -m "feat: add local infrastructure and worker skeleton"
```
