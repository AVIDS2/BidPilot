from fastapi.testclient import TestClient

from app.main import app


def test_list_scenarios() -> None:
    client = TestClient(app)
    response = client.get("/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    keys = [s["key"] for s in data]
    assert "bidpilot" in keys
    assert "contractpilot" in keys
    # Each scenario has key, label, description
    for s in data:
        assert "key" in s
        assert "label" in s
        assert "description" in s


def test_get_scenario_detail() -> None:
    client = TestClient(app)
    resp = client.get("/scenarios/contractpilot")
    assert resp.status_code == 200
    data = resp.json()
    assert data["key"] == "contractpilot"
    assert "default_sections" in data
    assert "requirement_keywords" in data


def test_get_scenario_sections() -> None:
    client = TestClient(app)
    resp = client.get("/scenarios/contractpilot/sections")
    assert resp.status_code == 200
    sections = resp.json()
    assert len(sections) > 0
    keys = [s["section_key"] for s in sections]
    assert "scope-of-work" in keys


def test_contractpilot_project_creates_sections() -> None:
    """Creating a ContractPilot project auto-creates default sections."""
    client = TestClient(app)
    proj = client.post("/projects", json={"name": "Contract Review", "scenario_package": "contractpilot"})
    assert proj.status_code == 201
    project_id = proj.json()["id"]

    # Check deliverable and sections were auto-created
    deliverables = client.get(f"/deliverables?project_id={project_id}")
    assert deliverables.status_code == 200
    assert len(deliverables.json()) >= 1

    dlv_id = deliverables.json()[0]["id"]
    sections = client.get(f"/deliverables/{dlv_id}/sections")
    assert sections.status_code == 200
    section_keys = [s["section_key"] for s in sections.json()]
    assert "scope-of-work" in section_keys
    assert "risk-assessment" in section_keys
