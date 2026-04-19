# DocPilot Phase 2 Governance and Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** add review flow, auditability, observability, and deployment mechanics so DocPilot becomes an operationally credible system

**Architecture:** keep review and audit in the control plane, surface traces and cost data through read models, and add deployment automation without changing the core domain model. Production credibility comes from strong state, not from more agent complexity.

**Tech Stack:** FastAPI, PostgreSQL, React, OpenTelemetry, Langfuse, Docker Compose, GitHub Actions, Celery

---

### Task 1: Add section review workflow

**Files:**
- Create: `services/api/app/review/schemas.py`
- Create: `services/api/app/review/router.py`
- Modify: `services/api/app/main.py`
- Create: `services/api/tests/review/test_submit_review_decision.py`
- Create: `apps/web/src/features/review/review-panel.tsx`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_submit_review_decision() -> None:
    client = TestClient(app)
    response = client.post(
        "/review/decisions",
        json={
            "section_id": "section-1",
            "decision": "approve",
            "comment": "Looks good",
        },
    )
    assert response.status_code == 201
    assert response.json()["decision"] == "approve"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory services/api pytest services/api/tests/review/test_submit_review_decision.py -v`
Expected: FAIL because the route does not exist

- [ ] **Step 3: Write minimal implementation**

```python
from pydantic import BaseModel


class ReviewDecisionCreate(BaseModel):
    section_id: str
    decision: str
    comment: str


class ReviewDecisionRead(ReviewDecisionCreate):
    id: str
```

```python
from uuid import uuid4

from fastapi import APIRouter, status

from .schemas import ReviewDecisionCreate, ReviewDecisionRead

router = APIRouter(prefix="/review", tags=["review"])


@router.post("/decisions", response_model=ReviewDecisionRead, status_code=status.HTTP_201_CREATED)
def submit_review_decision(payload: ReviewDecisionCreate) -> ReviewDecisionRead:
    return ReviewDecisionRead(id=str(uuid4()), **payload.model_dump())
```

```tsx
export function ReviewPanel() {
  return <aside>Review</aside>;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory services/api pytest services/api/tests/review/test_submit_review_decision.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/api apps/web
git commit -m "feat: add section review workflow"
```

### Task 2: Add audit events and trace correlation

**Files:**
- Create: `services/api/app/audit/service.py`
- Create: `services/api/app/audit/router.py`
- Modify: `services/api/app/main.py`
- Create: `services/api/tests/audit/test_list_audit_events.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_list_audit_events() -> None:
    client = TestClient(app)
    response = client.get("/audit/events", params={"project_id": "p1"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory services/api pytest services/api/tests/audit/test_list_audit_events.py -v`
Expected: FAIL because the route does not exist

- [ ] **Step 3: Write minimal implementation**

```python
def list_audit_events(project_id: str) -> list[dict[str, str]]:
    return [
        {
            "project_id": project_id,
            "event_type": "review.approved",
            "trace_id": "trace-demo",
        }
    ]
```

```python
from fastapi import APIRouter

from .service import list_audit_events

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events")
def get_audit_events(project_id: str) -> list[dict[str, str]]:
    return list_audit_events(project_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory services/api pytest services/api/tests/audit/test_list_audit_events.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/api
git commit -m "feat: add audit event read model"
```

### Task 3: Add deployment automation and smoke checks

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `scripts/smoke.sh`
- Create: `services/api/tests/test_openapi_smoke.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_openapi_schema_available() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "paths" in response.json()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory services/api pytest services/api/tests/test_openapi_smoke.py -v`
Expected: FAIL if OpenAPI export is misconfigured or app import is broken

- [ ] **Step 3: Write minimal implementation**

```yaml
name: ci

on:
  push:
  pull_request:

jobs:
  api-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install uv
      - run: uv run --directory services/api pytest -q
```

```bash
#!/usr/bin/env bash
set -euo pipefail

curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/openapi.json > /dev/null
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory services/api pytest services/api/tests/test_openapi_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml scripts/smoke.sh services/api/tests/test_openapi_smoke.py
git commit -m "chore: add ci and smoke checks"
```
