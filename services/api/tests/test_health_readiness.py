from fastapi.testclient import TestClient

import app.health as health_module
from app.main import app


def test_readiness_returns_safe_ready_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        health_module,
        "collect_dependency_checks",
        lambda _db: {"postgres": "ok", "redis": "ok", "minio": "ok"},
    )

    response = TestClient(app).get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"postgres": "ok", "redis": "ok", "minio": "ok"},
    }


def test_readiness_returns_safe_503_payload_when_a_dependency_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        health_module,
        "collect_dependency_checks",
        lambda _db: {"postgres": "ok", "redis": "unavailable", "minio": "ok"},
    )

    response = TestClient(app).get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"postgres": "ok", "redis": "unavailable", "minio": "ok"},
    }
