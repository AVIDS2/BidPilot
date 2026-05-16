"""Test health-detailed endpoint includes worker check."""


def test_health_detailed_includes_worker(client):
    resp = client.get("/ops/health-detailed")
    assert resp.status_code == 200
    data = resp.json()
    assert "checks" in data
    assert "worker" in data["checks"]
    assert data["checks"]["worker"]["status"] in ("ok", "error", "degraded")
