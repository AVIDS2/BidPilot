"""Test provider configuration CRUD API."""
from app.models import ProviderConfig
from app.security.secrets import decrypt_secret, is_encrypted_secret


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
    assert data["provider_id"] == "openai"
    assert "****" in data["api_key"]  # Masked


def test_create_provider_config_encrypts_api_key(client, default_org_id, default_user_id, test_db):
    """Provider keys should be encrypted before they are stored."""
    resp = client.post(
        "/auth/me/providers",
        json={
            "provider_type": "openai",
            "api_key": "test-provider-key",
            "model": "gpt-4o-mini",
            "label": "Encrypted",
        },
    )
    assert resp.status_code == 201
    config_id = resp.json()["data"]["id"]

    config = test_db.get(ProviderConfig, config_id)
    assert config is not None
    assert is_encrypted_secret(config.api_key)
    assert "test-provider-key" not in config.api_key
    assert decrypt_secret(config.api_key) == "test-provider-key"


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


def test_list_models_openai_compatible_payload(client, default_org_id, default_user_id, monkeypatch):
    """POST /auth/me/providers/models should list OpenAI-compatible models without storing the key."""

    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "data": [
                    {"id": "deepseek-chat", "owned_by": "deepseek"},
                    {"id": "deepseek-reasoner"},
                ]
            }

    captured = {}

    def fake_get(url, headers, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("app.providers.service.httpx.get", fake_get)

    resp = client.post(
        "/auth/me/providers/models",
        json={
            "provider_type": "openai",
            "api_key": "sk-runtime-only",
            "api_url": "https://api.deepseek.com",
        },
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert [model["id"] for model in data["models"]] == ["deepseek-chat", "deepseek-reasoner"]
    assert captured["url"] == "https://api.deepseek.com/models"
    assert captured["headers"]["Authorization"] == "Bearer sk-runtime-only"


def test_list_models_uses_stored_encrypted_config(client, default_org_id, default_user_id, monkeypatch):
    """Saved provider configs should use the encrypted server-side key for model listing."""
    create_resp = client.post(
        "/auth/me/providers",
        json={
            "provider_type": "anthropic",
            "api_key": "sk-ant-stored",
            "model": "claude-sonnet-4-20250514",
            "label": "My Claude",
        },
    )
    config_id = create_resp.json()["data"]["id"]

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"data": [{"id": "claude-sonnet-4-20250514", "display_name": "Claude Sonnet 4"}]}

    captured = {}

    def fake_get(url, headers, timeout):
        captured["url"] = url
        captured["headers"] = headers
        return FakeResponse()

    monkeypatch.setattr("app.providers.service.httpx.get", fake_get)

    resp = client.post("/auth/me/providers/models", json={"config_id": config_id})

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["models"][0]["id"] == "claude-sonnet-4-20250514"
    assert data["models"][0]["name"] == "Claude Sonnet 4"
    assert captured["url"] == "https://api.anthropic.com/v1/models"
    assert captured["headers"]["x-api-key"] == "sk-ant-stored"


def test_test_connection_uses_provider_specific_mimo_header(client, default_org_id, default_user_id, monkeypatch):
    class FakeResponse:
        status_code = 200

    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr("app.providers.service.httpx.post", fake_post)

    resp = client.post(
        "/auth/me/providers/test",
        json={
            "provider_type": "openai",
            "provider_id": "mimo",
            "api_key": "test-mimo-key",
            "api_url": "https://mimo.example.test/v1",
            "model": "mimo-v2.5-pro",
        },
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["success"] is True
    assert captured["url"] == "https://mimo.example.test/v1/chat/completions"
    assert captured["headers"] == {"api-key": "test-mimo-key", "content-type": "application/json"}


def test_manual_model_provider_returns_manual_discovery_state(client, default_org_id, default_user_id, monkeypatch):
    def should_not_call(*_args, **_kwargs):
        raise AssertionError("manual model discovery must not issue an undocumented request")

    monkeypatch.setattr("app.providers.service.httpx.get", should_not_call)

    resp = client.post(
        "/auth/me/providers/models",
        json={
            "provider_type": "openai",
            "provider_id": "dashscope",
            "api_key": "test-key",
            "api_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        },
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["models"] == []
    assert data["discovery_mode"] == "manual"
