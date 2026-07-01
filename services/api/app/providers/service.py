"""Provider configuration service -- CRUD for user API provider configs."""
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from app.models import ProviderConfig
from app.security.secrets import (
    SecretConfigurationError,
    decrypt_secret,
    encrypt_secret,
    mask_secret,
)

from .endpoints import normalize_provider_base_url, normalize_provider_endpoint
from .schemas import (
    ProviderConfigCreate,
    ProviderConfigUpdate,
    ProviderModelInfo,
    ProviderModelsRequest,
    ProviderModelsResponse,
    TestConnectionRequest,
    TestConnectionResponse,
)


def _mask_api_key(key: str) -> str:
    return mask_secret(key)


def list_provider_configs(db: Session, user_id: str) -> list[ProviderConfig]:
    return db.query(ProviderConfig).filter(ProviderConfig.user_id == user_id).order_by(ProviderConfig.created_at.desc()).all()


def get_provider_config(db: Session, config_id: str, user_id: str) -> ProviderConfig | None:
    return db.query(ProviderConfig).filter(ProviderConfig.id == config_id, ProviderConfig.user_id == user_id).first()


def create_provider_config(db: Session, user_id: str, payload: ProviderConfigCreate) -> ProviderConfig:
    encrypted_api_key = encrypt_secret(payload.api_key)

    # If setting this as active, deactivate others of same type
    if payload.is_active:
        db.query(ProviderConfig).filter(
            ProviderConfig.user_id == user_id,
            ProviderConfig.provider_type == payload.provider_type,
        ).update({"is_active": False})

    config = ProviderConfig(
        user_id=user_id,
        provider_type=payload.provider_type,
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

    if "is_active" in update_data and update_data["is_active"]:
        # Deactivate others of same type
        db.query(ProviderConfig).filter(
            ProviderConfig.user_id == user_id,
            ProviderConfig.provider_type == config.provider_type,
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
            return TestConnectionResponse(success=False, message="Provider config not found")
        provider_type = config.provider_type
        api_key = decrypt_secret(config.api_key)
        api_url = config.api_url
        model = config.model
    elif payload:
        provider_type = payload.provider_type
        api_key = payload.api_key
        api_url = payload.api_url
        model = payload.model
    else:
        return TestConnectionResponse(success=False, message="No provider config or payload provided")

    url = ""
    try:
        if provider_type == "anthropic":
            url = normalize_provider_endpoint(provider_type, api_url)
            resp = httpx.post(
                url,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "Say OK"}],
                },
                timeout=15.0,
            )
            if resp.status_code == 200:
                return TestConnectionResponse(success=True, message="Connection successful", model=model)
            elif resp.status_code == 401:
                return TestConnectionResponse(success=False, message="Authentication failed: invalid API key")
            else:
                return TestConnectionResponse(success=False, message=f"API error: {resp.status_code} {resp.text[:200]}")
        else:
            # OpenAI-compatible
            url = normalize_provider_endpoint(provider_type, api_url)
            resp = httpx.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "Say OK"}],
                },
                timeout=15.0,
            )
            if resp.status_code == 200:
                return TestConnectionResponse(success=True, message="Connection successful", model=model)
            elif resp.status_code == 401:
                return TestConnectionResponse(success=False, message="Authentication failed: invalid API key")
            else:
                return TestConnectionResponse(success=False, message=f"API error: {resp.status_code} {resp.text[:200]}")
    except httpx.ConnectError:
        return TestConnectionResponse(success=False, message=f"Cannot connect to {url}")
    except httpx.TimeoutException:
        return TestConnectionResponse(success=False, message="Connection timed out")
    except SecretConfigurationError:
        return TestConnectionResponse(success=False, message="Secret encryption key is not configured")
    except Exception as exc:
        return TestConnectionResponse(success=False, message=str(exc)[:200])


def list_provider_models(
    db: Session,
    user_id: str,
    payload: ProviderModelsRequest,
) -> ProviderModelsResponse:
    """List models through the backend so provider keys never reach browser-side APIs."""
    provider_type, api_key, api_url = _resolve_model_list_credentials(db, user_id, payload)
    base_url = normalize_provider_base_url(provider_type, api_url)
    if provider_type == "anthropic":
        url = f"{base_url}/v1/models"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
    else:
        url = f"{base_url}/models"
        headers = {"Authorization": f"Bearer {api_key}"}

    try:
        resp = httpx.get(url, headers=headers, timeout=15.0)
    except httpx.ConnectError as exc:
        raise ValueError(f"Cannot connect to {url}") from exc
    except httpx.TimeoutException as exc:
        raise ValueError("Model list request timed out") from exc

    if resp.status_code == 401:
        raise ValueError("Authentication failed: invalid API key")
    if resp.status_code >= 400:
        raise ValueError(f"API error: {resp.status_code} {resp.text[:200]}")

    try:
        data = resp.json()
    except ValueError as exc:
        raise ValueError("Provider returned invalid JSON") from exc

    return ProviderModelsResponse(models=_parse_model_list(data))


def _resolve_model_list_credentials(
    db: Session,
    user_id: str,
    payload: ProviderModelsRequest,
) -> tuple[str, str, str | None]:
    if payload.config_id:
        config = get_provider_config(db, payload.config_id, user_id)
        if config is None:
            raise ValueError("Provider config not found")
        return config.provider_type, decrypt_secret(config.api_key), config.api_url

    if not payload.provider_type or not payload.api_key:
        raise ValueError("Provider type and API key are required")
    return payload.provider_type, payload.api_key, payload.api_url


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
        "api_key": _mask_api_key(config.api_key),
        "api_url": config.api_url,
        "model": config.model,
        "label": config.label,
        "is_active": config.is_active,
        "created_at": config.created_at.isoformat() if config.created_at else None,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }
    return data
