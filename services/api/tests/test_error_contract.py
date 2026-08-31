from __future__ import annotations


def _assert_error_contract(response) -> dict:
    payload = response.json()
    assert set(("code", "message", "details", "request_id")).issubset(payload)
    assert payload["code"] == payload["error"]
    assert isinstance(payload["request_id"], str) and payload["request_id"]
    assert response.headers["x-request-id"] == payload["request_id"]
    return payload


def test_unknown_routes_use_the_public_error_contract(client) -> None:
    response = client.get("/does-not-exist")

    assert response.status_code == 404
    payload = _assert_error_contract(response)
    assert payload["code"] == "not_found"
    assert payload["message"] == "Not Found"


def test_request_validation_uses_safe_structured_details(client) -> None:
    response = client.post("/auth/login", json={})

    assert response.status_code == 422
    payload = _assert_error_contract(response)
    assert payload["code"] == "validation_error"
    assert payload["message"] == "请求参数无效"
    assert isinstance(payload["details"], list)
    assert all(set(item) == {"loc", "message", "type"} for item in payload["details"])
    assert all("input" not in item for item in payload["details"])
