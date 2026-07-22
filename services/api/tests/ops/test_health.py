"""Test health-detailed endpoint returns safe dependency state."""

import app.ops.router as ops_router


def test_health_detailed_includes_worker(client):
    resp = client.get("/ops/health-detailed")
    assert resp.status_code == 200
    data = resp.json()
    assert "checks" in data
    assert "worker" in data["checks"]
    assert data["checks"]["worker"]["status"] in ("ok", "unavailable", "degraded")


def test_health_detailed_never_returns_dependency_error_text(client, monkeypatch):
    monkeypatch.setattr(
        ops_router,
        "collect_dependency_checks",
        lambda _db, include_worker: {"postgres": "ok", "redis": "unavailable", "minio": "ok", "worker": "ok"},
    )

    response = client.get("/ops/health-detailed")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "checks": {
            "postgres": {"status": "ok"},
            "redis": {"status": "unavailable"},
            "minio": {"status": "ok"},
            "worker": {"status": "ok"},
        },
    }
