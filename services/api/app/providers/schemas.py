from datetime import datetime
from pydantic import BaseModel, Field


class ProviderConfigCreate(BaseModel):
    provider_type: str = Field(..., pattern="^(openai|anthropic)$")
    provider_id: str | None = Field(default=None, min_length=1, max_length=64)
    api_key: str = Field(..., min_length=1)
    api_url: str | None = None
    model: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1, max_length=100)
    is_active: bool = False


class ProviderConfigUpdate(BaseModel):
    provider_type: str | None = Field(default=None, pattern="^(openai|anthropic)$")
    provider_id: str | None = Field(default=None, min_length=1, max_length=64)
    api_key: str | None = None
    api_url: str | None = None
    model: str | None = None
    label: str | None = None
    is_active: bool | None = None


class ProviderConfigRead(BaseModel):
    id: str
    user_id: str
    provider_type: str
    provider_id: str
    api_key: str  # Mask in response
    api_url: str | None
    model: str
    label: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TestConnectionRequest(BaseModel):
    provider_type: str = Field(..., pattern="^(openai|anthropic)$")
    provider_id: str | None = Field(default=None, min_length=1, max_length=64)
    api_key: str = Field(..., min_length=1)
    api_url: str | None = None
    model: str = Field(..., min_length=1)


class TestConnectionResponse(BaseModel):
    success: bool
    message: str
    model: str | None = None
    code: str | None = None


class ProviderModelsRequest(BaseModel):
    config_id: str | None = None
    provider_type: str | None = Field(default=None, pattern="^(openai|anthropic)$")
    provider_id: str | None = Field(default=None, min_length=1, max_length=64)
    api_key: str | None = None
    api_url: str | None = None


class ProviderModelInfo(BaseModel):
    id: str
    name: str | None = None
    owned_by: str | None = None


class ProviderModelsResponse(BaseModel):
    models: list[ProviderModelInfo]
    discovery_mode: str = "supported"
    message: str | None = None
