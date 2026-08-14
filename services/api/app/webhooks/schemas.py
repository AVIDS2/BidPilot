from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


WebhookEventType = Literal[
    "radar.notice.matched",
    "radar.notice.saved",
    "radar.notice.converted",
]
WebhookDeliveryStatus = Literal["pending", "delivering", "delivered", "failed"]


class WebhookEndpointCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=160)
    target_url: str = Field(min_length=8, max_length=2048)
    events: list[WebhookEventType] = Field(min_length=1, max_length=3)


class WebhookEndpointUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=160)
    target_url: str | None = Field(default=None, min_length=8, max_length=2048)
    events: list[WebhookEventType] | None = Field(default=None, min_length=1, max_length=3)
    is_active: bool | None = None


class WebhookEndpointRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    target_url: str
    events: list[WebhookEventType]
    is_active: bool
    signing_secret_hint: str
    created_at: datetime | None
    updated_at: datetime | None


class WebhookEndpointCreateRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint: WebhookEndpointRead
    signing_secret: str


class WebhookDeliveryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    endpoint_id: str
    endpoint_name: str
    event_type: str
    status: WebhookDeliveryStatus
    attempt_count: int
    max_attempts: int
    available_at: datetime | None
    last_http_status: int | None
    last_error_code: str | None
    delivered_at: datetime | None
    created_at: datetime | None
    payload: dict


class WebhookOverviewSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_endpoint_count: int
    delivery_count: int
    failed_delivery_count: int
    pending_delivery_count: int


class WebhookOverviewRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: WebhookOverviewSummary
    supported_events: list[WebhookEventType]
    endpoints: list[WebhookEndpointRead]
    deliveries: list[WebhookDeliveryRead]


class WebhookDeliveryActionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delivery: WebhookDeliveryRead
