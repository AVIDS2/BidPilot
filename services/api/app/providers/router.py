"""Provider configuration API -- users manage their own AI provider keys."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.service import require_auth
from app.security.secrets import SecretConfigurationError
from .schemas import (
    ProviderConfigCreate, ProviderConfigUpdate,
    TestConnectionRequest,
)
from .service import (
    list_provider_configs, get_provider_config, create_provider_config,
    update_provider_config, delete_provider_config, test_connection, mask_read_config,
)

router = APIRouter(prefix="/auth/me/providers", tags=["providers"], dependencies=[Depends(require_auth)])


@router.get("")
def list_providers(user=Depends(require_auth), db: Session = Depends(get_db)):
    """List all provider configurations for the current user."""
    configs = list_provider_configs(db, user.id)
    return {"data": [mask_read_config(c) for c in configs]}


@router.post("", status_code=201)
def create_provider(payload: ProviderConfigCreate, user=Depends(require_auth), db: Session = Depends(get_db)):
    """Create a new provider configuration."""
    try:
        config = create_provider_config(db, user.id, payload)
    except SecretConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"data": mask_read_config(config)}


@router.get("/{config_id}")
def get_provider(config_id: str, user=Depends(require_auth), db: Session = Depends(get_db)):
    """Get a specific provider configuration."""
    config = get_provider_config(db, config_id, user.id)
    if config is None:
        raise HTTPException(status_code=404, detail="Provider config not found")
    return {"data": mask_read_config(config)}


@router.put("/{config_id}")
def update_provider(config_id: str, payload: ProviderConfigUpdate, user=Depends(require_auth), db: Session = Depends(get_db)):
    """Update a provider configuration."""
    try:
        config = update_provider_config(db, config_id, user.id, payload)
    except SecretConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if config is None:
        raise HTTPException(status_code=404, detail="Provider config not found")
    return {"data": mask_read_config(config)}


@router.delete("/{config_id}")
def delete_provider(config_id: str, user=Depends(require_auth), db: Session = Depends(get_db)):
    """Delete a provider configuration."""
    deleted = delete_provider_config(db, config_id, user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Provider config not found")
    return {"data": {"deleted": True}}


@router.post("/test")
def test_provider_connection(
    payload: TestConnectionRequest | None = None,
    config_id: str | None = None,
    user=Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Test a provider connection."""
    result = test_connection(db, user.id, config_id, payload)
    return {"data": result.model_dump()}
