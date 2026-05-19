from datetime import datetime
from pydantic import BaseModel, Field


class ProviderConfigCreate(BaseModel):
    provider_type: str = Field(..., pattern="^(openai|anthropic)$")
    api_key: str = Field(..., min_length=1)
    api_url: str | None = None
    model: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1, max_length=100)
    is_active: bool = False


class ProviderConfigUpdate(BaseModel):
    api_key: str | None = None
    api_url: str | None = None
    model: str | None = None
    label: str | None = None
    is_active: bool | None = None


class ProviderConfigRead(BaseModel):
    id: str
    user_id: str
    provider_type: str
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
    api_key: str = Field(..., min_length=1)
    api_url: str | None = None
    model: str = Field(..., min_length=1)


class TestConnectionResponse(BaseModel):
    success: bool
    message: str
    model: str | None = None
