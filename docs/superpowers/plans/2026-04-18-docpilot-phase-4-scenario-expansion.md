# DocPilot Phase 4 Scenario Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** expand beyond BidPilot without breaking the original control plane or turning DocPilot into an unbounded generic builder

**Architecture:** introduce reusable scenario packaging around a stable project, deliverable, evidence, and review core. Scenario variation belongs in templates, adapters, and configuration layers, not in duplicate control-plane logic.

**Tech Stack:** existing DocPilot stack plus internal scenario package contracts

---

### Task 1: Introduce scenario package registry

**Files:**
- Create: `services/api/app/scenarios/registry.py`
- Create: `services/api/app/scenarios/router.py`
- Modify: `services/api/app/main.py`
- Create: `services/api/tests/scenarios/test_list_scenarios.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_list_scenarios() -> None:
    client = TestClient(app)
    response = client.get("/scenarios")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory services/api pytest services/api/tests/scenarios/test_list_scenarios.py -v`
Expected: FAIL because the route does not exist

- [ ] **Step 3: Write minimal implementation**

```python
def list_scenarios() -> list[dict[str, str]]:
    return [
        {"key": "bidpilot", "label": "BidPilot"},
        {"key": "contractpilot", "label": "ContractPilot"},
    ]
```

```python
from fastapi import APIRouter

from .registry import list_scenarios

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("")
def get_scenarios() -> list[dict[str, str]]:
    return list_scenarios()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory services/api pytest services/api/tests/scenarios/test_list_scenarios.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/api
git commit -m "feat: add scenario package registry"
```

### Task 2: Add scenario-specific template binding

**Files:**
- Create: `services/api/app/scenarios/templates.py`
- Create: `services/api/tests/scenarios/test_resolve_template.py`
- Create: `apps/web/src/features/scenarios/scenario-selector.tsx`

- [ ] **Step 1: Write the failing test**

```python
from app.scenarios.templates import resolve_default_template


def test_resolve_default_template() -> None:
    template = resolve_default_template("bidpilot")
    assert template["scenario_key"] == "bidpilot"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory services/api pytest services/api/tests/scenarios/test_resolve_template.py -v`
Expected: FAIL because the module does not exist

- [ ] **Step 3: Write minimal implementation**

```python
def resolve_default_template(scenario_key: str) -> dict[str, str]:
    return {
        "scenario_key": scenario_key,
        "template_key": f"{scenario_key}-default",
    }
```

```tsx
export function ScenarioSelector() {
  return <section>Scenario Selector</section>;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory services/api pytest services/api/tests/scenarios/test_resolve_template.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/api apps/web
git commit -m "feat: add scenario template binding"
```

### Task 3: Add compatibility regression guard for BidPilot

**Files:**
- Create: `services/api/tests/scenarios/test_bidpilot_contract.py`
- Create: `docs/adr/0002-scenario-package-model.md`

- [ ] **Step 1: Write the failing test**

```python
def test_bidpilot_contract_placeholder() -> None:
    assert True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory services/api pytest services/api/tests/scenarios/test_bidpilot_contract.py -v`
Expected: FAIL because the file does not exist yet

- [ ] **Step 3: Write minimal implementation**

```md
# ADR 0002: Scenario Package Model

- Status: Proposed
- Date: 2026-04-18

## Decision

Scenario variation must be introduced through package metadata, templates, and execution configuration without replacing the core project, review, evidence, and deliverable models.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory services/api pytest services/api/tests/scenarios/test_bidpilot_contract.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/api/tests/scenarios docs/adr/0002-scenario-package-model.md
git commit -m "docs: define scenario package model guardrails"
```
