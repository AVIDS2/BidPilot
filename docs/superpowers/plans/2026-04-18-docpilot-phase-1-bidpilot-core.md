# DocPilot Phase 1 BidPilot Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** build the first end-to-end BidPilot workflow from project creation to evidence-backed drafting

**Architecture:** keep the control plane in FastAPI plus PostgreSQL and use the worker for ingestion, parsing, retrieval, and drafting jobs. Add thin execution endpoints in the API but persist every meaningful run and output state back into relational storage.

**Tech Stack:** FastAPI, SQLAlchemy 2, PostgreSQL, Celery, Redis, pgvector, React, TanStack Query, TipTap, LangGraph

---

### Task 1: Add project workspace and project CRUD

**Files:**
- Create: `services/api/app/projects/schemas.py`
- Create: `services/api/app/projects/router.py`
- Modify: `services/api/app/main.py`
- Create: `services/api/tests/projects/test_create_project.py`
- Create: `apps/web/src/features/projects/project-list.tsx`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_create_project() -> None:
    client = TestClient(app)
    response = client.post(
        "/projects",
        json={"name": "Acme Bid", "scenario_package": "bidpilot"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Acme Bid"
    assert data["scenario_package"] == "bidpilot"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory services/api pytest services/api/tests/projects/test_create_project.py -v`
Expected: FAIL because the route does not exist

- [ ] **Step 3: Write minimal implementation**

```python
from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    scenario_package: str


class ProjectRead(ProjectCreate):
    id: str
```

```python
from uuid import uuid4

from fastapi import APIRouter, status

from .schemas import ProjectCreate, ProjectRead

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate) -> ProjectRead:
    return ProjectRead(id=str(uuid4()), **payload.model_dump())
```

```python
from fastapi import FastAPI

from app.projects.router import router as projects_router

app = FastAPI(title="DocPilot API")
app.include_router(projects_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

```tsx
export function ProjectList() {
  return <section>Projects</section>;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory services/api pytest services/api/tests/projects/test_create_project.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/api apps/web
git commit -m "feat: add project workspace api"
```

### Task 2: Add bundle upload registry and ingest scheduling

**Files:**
- Create: `services/api/app/bundles/schemas.py`
- Create: `services/api/app/bundles/router.py`
- Modify: `services/api/app/main.py`
- Create: `services/worker/app/ingest.py`
- Create: `services/api/tests/bundles/test_register_bundle.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_register_bundle() -> None:
    client = TestClient(app)
    response = client.post(
        "/bundles",
        json={"project_id": "p1", "label": "RFP Pack", "source_type": "upload"},
    )
    assert response.status_code == 201
    assert response.json()["label"] == "RFP Pack"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory services/api pytest services/api/tests/bundles/test_register_bundle.py -v`
Expected: FAIL because the route does not exist

- [ ] **Step 3: Write minimal implementation**

```python
from pydantic import BaseModel


class BundleCreate(BaseModel):
    project_id: str
    label: str
    source_type: str


class BundleRead(BundleCreate):
    id: str
    ingest_status: str
```

```python
from uuid import uuid4

from fastapi import APIRouter, status

from .schemas import BundleCreate, BundleRead

router = APIRouter(prefix="/bundles", tags=["bundles"])


@router.post("", response_model=BundleRead, status_code=status.HTTP_201_CREATED)
def register_bundle(payload: BundleCreate) -> BundleRead:
    return BundleRead(
        id=str(uuid4()),
        ingest_status="queued",
        **payload.model_dump(),
    )
```

```python
def schedule_ingest(bundle_id: str) -> dict[str, str]:
    return {"bundle_id": bundle_id, "status": "queued"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory services/api pytest services/api/tests/bundles/test_register_bundle.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/api services/worker
git commit -m "feat: add bundle registry and ingest scheduling"
```

### Task 3: Add evidence-backed section drafting

**Files:**
- Create: `services/api/app/drafting/schemas.py`
- Create: `services/api/app/drafting/router.py`
- Create: `services/worker/app/drafting.py`
- Create: `services/api/tests/drafting/test_generate_section.py`
- Create: `apps/web/src/features/drafting/section-editor.tsx`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_generate_section() -> None:
    client = TestClient(app)
    response = client.post(
        "/drafting/sections",
        json={"project_id": "p1", "section_key": "technical-approach"},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory services/api pytest services/api/tests/drafting/test_generate_section.py -v`
Expected: FAIL because the route does not exist

- [ ] **Step 3: Write minimal implementation**

```python
from pydantic import BaseModel


class DraftSectionRequest(BaseModel):
    project_id: str
    section_key: str


class DraftSectionResponse(BaseModel):
    run_id: str
    status: str
```

```python
from uuid import uuid4

from fastapi import APIRouter, status

from .schemas import DraftSectionRequest, DraftSectionResponse

router = APIRouter(prefix="/drafting", tags=["drafting"])


@router.post("/sections", response_model=DraftSectionResponse, status_code=status.HTTP_202_ACCEPTED)
def draft_section(payload: DraftSectionRequest) -> DraftSectionResponse:
    return DraftSectionResponse(run_id=str(uuid4()), status="queued")
```

```python
def generate_section(project_id: str, section_key: str) -> dict[str, object]:
    return {
        "project_id": project_id,
        "section_key": section_key,
        "markdown": "Generated section",
        "evidence_ids": [],
    }
```

```tsx
export function SectionEditor() {
  return <section>Section Draft</section>;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory services/api pytest services/api/tests/drafting/test_generate_section.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/api services/worker apps/web
git commit -m "feat: add evidence-backed section drafting entrypoint"
```
