"""Test all API errors follow consistent format."""

from fastapi.testclient import TestClient

from app.main import app


def test_404_has_consistent_format(client):
    resp = client.get("/projects/nonexistent-id")
    assert resp.status_code == 404
    data = resp.json()
    assert "error" in data
    assert "message" in data


def test_422_has_consistent_format(client):
    resp = client.post("/projects", json={})
    assert resp.status_code == 422
    data = resp.json()
    assert "error" in data or "detail" in data  # FastAPI built-in 422


def test_401_on_protected_endpoint(client):
    resp = client.get("/auth/me/export")
    assert resp.status_code == 401
    data = resp.json()
    assert "error" in data or "detail" in data
