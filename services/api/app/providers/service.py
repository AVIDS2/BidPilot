"""Provider configuration service -- CRUD for user API provider configs."""
from datetime import UTC, datetime

import httpx
import os
from sqlalchemy.orm import Session

from app.models import ProviderConfig
from app.security.secrets import (
    SecretConfigurationError,
    decrypt_secret,
    encrypt_secret,
    mask_secret,
)

from .endpoints import (
    ProviderProfileError,
    get_provider_profile,
    infer_provider_id,
    normalize_provider_base_url,
    resolve_provider_chat_request,
    resolve_provider_model_list_request,
)
from .schemas import (
    ProviderConfigCreate,
    ProviderConfigUpdate,
    ProviderModelInfo,
    ProviderModelsRequest,
    ProviderModelsResponse,
    TestConnectionRequest,
    TestConnectionResponse,
    PiModelCatalogResponse,
)


def _mask_api_key(key: str) -> str:
    return mask_secret(key)


def list_provider_configs(db: Session, user_id: str) -> list[ProviderConfig]:
    return db.query(ProviderConfig).filter(ProviderConfig.user_id == user_id).order_by(ProviderConfig.created_at.desc()).all()


def get_provider_config(db: Session, config_id: str, user_id: str) -> ProviderConfig | None:
    return db.query(ProviderConfig).filter(ProviderConfig.id == config_id, ProviderConfig.user_id == user_id).first()


def create_provider_config(db: Session, user_id: str, payload: ProviderConfigCreate) -> ProviderConfig:
    encrypted_api_key = encrypt_secret(payload.api_key)
    provider_id = _resolve_provider_id(payload.provider_type, payload.provider_id, payload.api_url)

    # If setting this as active, deactivate others of same type
    if payload.is_active:
        db.query(ProviderConfig).filter(
            ProviderConfig.user_id == user_id,
            ProviderConfig.provider_type == payload.provider_type,
        ).update({"is_active": False})

    config = ProviderConfig(
        user_id=user_id,
        provider_type=payload.provider_type,
        provider_id=provider_id,
        api_key=encrypted_api_key,
        api_url=payload.api_url,
        model=payload.model,
        label=payload.label,
        is_active=payload.is_active,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def update_provider_config(db: Session, config_id: str, user_id: str, payload: ProviderConfigUpdate) -> ProviderConfig | None:
    config = get_provider_config(db, config_id, user_id)
    if config is None:
        return None

    update_data = payload.model_dump(exclude_unset=True)
    if "api_key" in update_data and update_data["api_key"]:
        update_data["api_key"] = encrypt_secret(update_data["api_key"])

    target_provider_type = update_data.get("provider_type", config.provider_type)
    target_api_url = update_data.get("api_url", config.api_url)
    target_provider_id = _resolve_provider_id(
        target_provider_type,
        update_data.get("provider_id", config.provider_id),
        target_api_url,
    )
    update_data["provider_id"] = target_provider_id

    if update_data.get("is_active", config.is_active):
        # Deactivate other active configurations for the target protocol.
        db.query(ProviderConfig).filter(
            ProviderConfig.user_id == user_id,
            ProviderConfig.provider_type == target_provider_type,
            ProviderConfig.id != config_id,
        ).update({"is_active": False})

    for key, value in update_data.items():
        setattr(config, key, value)

    config.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(config)
    return config


def delete_provider_config(db: Session, config_id: str, user_id: str) -> bool:
    config = get_provider_config(db, config_id, user_id)
    if config is None:
        return False
    db.delete(config)
    db.commit()
    return True


def test_connection(db: Session, user_id: str, config_id: str | None, payload: TestConnectionRequest | None) -> TestConnectionResponse:
    """Test a provider connection. If config_id is given, test from DB. Otherwise test from payload."""
    if config_id:
        config = get_provider_config(db, config_id, user_id)
        if config is None:
            return TestConnectionResponse(success=False, message="Provider config not found", code="provider_config_missing")
        provider_type = config.provider_type
        provider_id = config.provider_id
        api_key = decrypt_secret(config.api_key)
        api_url = config.api_url
        model = config.model
    elif payload:
        provider_type = payload.provider_type
        provider_id = payload.provider_id or infer_provider_id(payload.provider_type, payload.api_url)
        api_key = payload.api_key
        api_url = payload.api_url
        model = payload.model
    else:
        return TestConnectionResponse(
            success=False,
            message="No provider config or payload provided",
            code="provider_config_missing",
        )

    try:
        request = resolve_provider_chat_request(provider_type, provider_id, api_url, api_key)
        if provider_type == "anthropic":
            body: dict[str, object] = {
                "model": model,
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "Say OK"}],
            }
        else:
            body = {
                "model": model,
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "Say OK"}],
            }
        resp = httpx.post(request.url, headers=request.headers, json=body, timeout=15.0)
        if resp.status_code == 200:
            return TestConnectionResponse(success=True, message="Connection successful", model=model)
        return _connection_status_error(resp.status_code)
    except httpx.ConnectError:
        return TestConnectionResponse(
            success=False,
            message="Cannot connect to the configured provider endpoint",
            code="provider_unavailable",
        )
    except httpx.TimeoutException:
        return TestConnectionResponse(success=False, message="Connection timed out", code="provider_timeout")
    except SecretConfigurationError:
        return TestConnectionResponse(
            success=False,
            message="Secret encryption key is not configured",
            code="provider_secret_unavailable",
        )
    except ProviderProfileError as exc:
        return TestConnectionResponse(success=False, message=str(exc), code=exc.code)
    except httpx.RequestError:
        return TestConnectionResponse(
            success=False,
            message="Provider request could not be completed",
            code="provider_unavailable",
        )


def list_provider_models(
    db: Session,
    user_id: str,
    payload: ProviderModelsRequest,
) -> ProviderModelsResponse:
    """List models through the backend so provider keys never reach browser-side APIs."""
    provider_type, provider_id, api_key, api_url = _resolve_model_list_credentials(db, user_id, payload)
    request = resolve_provider_model_list_request(provider_type, provider_id, api_url, api_key)
    if request is None:
        return ProviderModelsResponse(
            models=[],
            discovery_mode="manual",
            message="This provider requires selecting a model or endpoint identifier from its console.",
        )

    try:
        resp = httpx.get(request.url, headers=request.headers, timeout=15.0)
    except httpx.ConnectError as exc:
        raise ValueError("Cannot connect to the configured provider endpoint") from exc
    except httpx.TimeoutException as exc:
        raise ValueError("Model list request timed out") from exc

    if resp.status_code in {401, 403}:
        raise ValueError("Authentication failed: invalid API key")
    if resp.status_code >= 400:
        if request.profile.model_discovery == "best_effort" and resp.status_code in {404, 405, 501}:
            return ProviderModelsResponse(
                models=[],
                discovery_mode="unsupported",
                message="This custom endpoint does not expose a standard model list. Enter the model name manually.",
            )
        raise ValueError(_provider_status_message(resp.status_code))

    try:
        data = resp.json()
    except ValueError as exc:
        raise ValueError("Provider returned invalid JSON") from exc

    return ProviderModelsResponse(models=_parse_model_list(data), discovery_mode="supported")


def list_pi_model_catalog() -> PiModelCatalogResponse:
    """Read the sidecar's native pi-ai catalog without forwarding user keys."""
    sidecar_url = os.environ.get("DOCPILOT_PI_AGENT_URL", "http://pi-agent:8787").rstrip("/")
    try:
        response = httpx.get(f"{sidecar_url}/v1/models/catalog", timeout=4.0)
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        raise ValueError("Pi model catalog is temporarily unavailable") from exc
    if response.status_code >= 400:
        raise ValueError("Pi model catalog is temporarily unavailable")
    try:
        return PiModelCatalogResponse.model_validate(response.json())
    except ValueError as exc:
        raise ValueError("Pi model catalog returned invalid data") from exc


def _resolve_model_list_credentials(
    db: Session,
    user_id: str,
    payload: ProviderModelsRequest,
) -> tuple[str, str, str, str | None]:
    if payload.config_id:
        config = get_provider_config(db, payload.config_id, user_id)
        if config is None:
            raise ValueError("Provider config not found")
        return config.provider_type, config.provider_id, decrypt_secret(config.api_key), config.api_url

    if not payload.provider_type or not payload.api_key:
        raise ValueError("Provider type and API key are required")
    provider_id = _resolve_provider_id(payload.provider_type, payload.provider_id, payload.api_url)
    return payload.provider_type, provider_id, payload.api_key, payload.api_url


def _resolve_provider_id(provider_type: str, provider_id: str | None, api_url: str | None) -> str:
    """Validate a requested profile and reject missing required endpoint data."""
    resolved_id = provider_id or infer_provider_id(provider_type, api_url)
    profile = get_provider_profile(resolved_id, provider_type)
    # Resolve once during writes so a profile that requires a console-provided
    # base URL cannot silently fall through to an unrelated public endpoint.
    normalize_provider_base_url(provider_type, api_url, profile.id)
    return profile.id


def _connection_status_error(status_code: int) -> TestConnectionResponse:
    if status_code in {401, 403}:
        return TestConnectionResponse(
            success=False,
            message="Authentication failed: verify the API key and account permissions",
            code="provider_auth_failed",
        )
    return TestConnectionResponse(
        success=False,
        message=_provider_status_message(status_code),
        code=_provider_status_code(status_code),
    )


def _provider_status_code(status_code: int) -> str:
    if status_code == 404:
        return "provider_model_unavailable"
    if status_code in {400, 422}:
        return "provider_request_invalid"
    if status_code == 429:
        return "provider_rate_limited"
    if status_code >= 500 or status_code in {408, 409}:
        return "provider_unavailable"
    return "provider_request_failed"


def _provider_status_message(status_code: int) -> str:
    code = _provider_status_code(status_code)
    messages = {
        "provider_model_unavailable": "Provider could not find the selected model or endpoint",
        "provider_request_invalid": "Provider rejected the request. Verify the protocol, base URL, and model name",
        "provider_rate_limited": "Provider rate limit reached. Try again shortly",
        "provider_unavailable": "Provider is temporarily unavailable. Try again shortly",
    }
    return messages.get(code, f"Provider request failed with HTTP {status_code}")


def _parse_model_list(data: object) -> list[ProviderModelInfo]:
    if isinstance(data, dict):
        raw_items = data.get("data") or data.get("models") or []
    elif isinstance(data, list):
        raw_items = data
    else:
        raw_items = []

    models: list[ProviderModelInfo] = []
    for item in raw_items:
        if isinstance(item, str):
            models.append(ProviderModelInfo(id=item))
            continue
        if not isinstance(item, dict):
            continue
        model_id = item.get("id") or item.get("name")
        if not model_id:
            continue
        display_name = item.get("display_name") or item.get("name")
        models.append(
            ProviderModelInfo(
                id=str(model_id),
                name=str(display_name) if display_name else None,
                owned_by=str(item.get("owned_by")) if item.get("owned_by") else None,
            )
        )
    return models


def mask_read_config(config: ProviderConfig) -> dict:
    """Return config dict with masked API key."""
    data = {
        "id": config.id,
        "user_id": config.user_id,
        "provider_type": config.provider_type,
        "provider_id": config.provider_id or infer_provider_id(config.provider_type, config.api_url),
        "api_key": _mask_api_key(config.api_key),
        "api_url": config.api_url,
        "model": config.model,
        "label": config.label,
        "is_active": config.is_active,
        "created_at": config.created_at.isoformat() if config.created_at else None,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }
    return data
