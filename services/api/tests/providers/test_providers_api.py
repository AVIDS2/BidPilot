"""Test provider configuration CRUD API."""
from app.models import ProviderConfig


def test_create_provider_config(client, default_org_id, default_user_id):
    """POST /auth/me/providers should create a new config."""
    resp = client.post(
        "/auth/me/providers",
        json={
            "provider_type": "openai",
            "api_key": "sk-test123",
            "api_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini",
            "label": "My OpenAI",
            "is_active": True,
        },
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["provider_type"] == "openai"
    assert "****" in data["api_key"]  # Masked


def test_list_provider_configs(client, default_org_id, default_user_id):
    """GET /auth/me/providers should list configs."""
    # Create one first
    client.post(
        "/auth/me/providers",
        json={"provider_type": "openai", "api_key": "sk-test456", "model": "gpt-4o", "label": "Test"},
    )
    resp = client.get("/auth/me/providers")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 1


def test_delete_provider_config(client, default_org_id, default_user_id):
    """DELETE /auth/me/providers/{id} should delete config."""
    create_resp = client.post(
        "/auth/me/providers",
        json={
            "provider_type": "anthropic",
            "api_key": "sk-ant-test",
            "model": "claude-sonnet-4-20250514",
            "label": "My Claude",
        },
    )
    config_id = create_resp.json()["data"]["id"]

    resp = client.delete(f"/auth/me/providers/{config_id}")
    assert resp.status_code == 200

    # Verify deleted
    get_resp = client.get(f"/auth/me/providers/{config_id}")
    assert get_resp.status_code == 404


def test_test_connection_endpoint(client, default_org_id, default_user_id):
    """POST /auth/me/providers/test should return a result (may fail without real key)."""
    resp = client.post(
        "/auth/me/providers/test",
        json={"provider_type": "openai", "api_key": "sk-invalid", "model": "gpt-4o-mini"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "success" in data
    assert data["success"] is False  # Invalid key should fail
