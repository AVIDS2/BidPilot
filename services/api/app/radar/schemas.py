from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


NoticeSourceKind = Literal["rss", "json_feed", "webhook"]
NoticeType = Literal["intent", "tender", "prequalification", "rfi", "other"]
NoticeStatus = Literal["new", "saved", "ignored", "converted"]


class NoticeSourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=160)
    kind: NoticeSourceKind
    endpoint_url: str | None = Field(default=None, min_length=8, max_length=2048)
    polling_interval_minutes: int = Field(default=60, ge=5, le=1440)

    @model_validator(mode="after")
    def validate_endpoint(self) -> "NoticeSourceCreate":
        if self.kind != "webhook" and not self.endpoint_url:
            raise ValueError("RSS 和 JSON Feed 来源需要提供公开地址")
        return self


class NoticeSourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=160)
    endpoint_url: str | None = Field(default=None, min_length=8, max_length=2048)
    polling_interval_minutes: int | None = Field(default=None, ge=5, le=1440)
    is_active: bool | None = None


class NoticeSourceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    kind: NoticeSourceKind
    endpoint_url: str | None
    is_active: bool
    polling_interval_minutes: int
    last_polled_at: datetime | None
    last_success_at: datetime | None
    last_error_code: str | None
    notice_count: int = 0


class NoticeSubscriptionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=160)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    regions: list[str] = Field(default_factory=list, max_length=12)
    categories: list[str] = Field(default_factory=list, max_length=12)
    budget_min: float | None = Field(default=None, ge=0)
    budget_max: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_budget_range(self) -> "NoticeSubscriptionCreate":
        if self.budget_min is not None and self.budget_max is not None and self.budget_min > self.budget_max:
            raise ValueError("预算下限不能高于预算上限")
        return self


class NoticeSubscriptionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=160)
    keywords: list[str] | None = Field(default=None, max_length=20)
    regions: list[str] | None = Field(default=None, max_length=12)
    categories: list[str] | None = Field(default=None, max_length=12)
    budget_min: float | None = Field(default=None, ge=0)
    budget_max: float | None = Field(default=None, ge=0)
    is_active: bool | None = None


class NoticeSubscriptionRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    keywords: list[str]
    regions: list[str]
    categories: list[str]
    budget_min: float | None
    budget_max: float | None
    is_active: bool
    match_count: int = 0
    created_at: datetime | None
    updated_at: datetime | None


class NoticeMatchRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subscription_id: str
    subscription_name: str
    score: int
    reasons: list[str]


class NoticeRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source_id: str
    source_name: str
    external_id: str
    title: str
    buyer_name: str | None
    notice_type: NoticeType
    region: str | None
    category: str | None
    budget_amount: float | None
    published_at: datetime | None
    deadline_at: datetime | None
    source_url: str
    summary: str | None
    status: NoticeStatus
    converted_project_id: str | None
    created_at: datetime | None
    matches: list[NoticeMatchRead]


class NoticeStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["saved", "ignored", "new"]


class NoticeProjectConvert(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    project_name: str | None = Field(default=None, min_length=1, max_length=255)


class NoticeProjectConvertRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notice: NoticeRead
    project_id: str
    project_slug: str


class NoticeSourceIngestItem(BaseModel):
    """Normalized handoff for an external connector or inbound webhook."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    external_id: str | None = Field(default=None, max_length=500)
    title: str = Field(min_length=1, max_length=500)
    source_url: str = Field(min_length=8, max_length=2048)
    buyer_name: str | None = Field(default=None, max_length=255)
    notice_type: NoticeType = "other"
    region: str | None = Field(default=None, max_length=120)
    category: str | None = Field(default=None, max_length=120)
    budget_amount: float | None = Field(default=None, ge=0)
    published_at: datetime | None = None
    deadline_at: datetime | None = None
    summary: str | None = Field(default=None, max_length=12000)
    source_snapshot: dict[str, object] | None = None


class NoticeSourceIngest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[NoticeSourceIngestItem] = Field(min_length=1, max_length=200)


class NoticePollRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    status: Literal["succeeded", "failed", "skipped"]
    discovered_count: int = 0
    created_count: int = 0
    updated_count: int = 0
    error_code: str | None = None


class RadarTrendPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day: str
    notice_count: int


class RadarSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_source_count: int
    source_attention_count: int
    active_subscription_count: int
    recommended_count: int
    saved_count: int
    due_soon_count: int
    trends: list[RadarTrendPoint]


class RadarOverviewRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: RadarSummaryRead
    sources: list[NoticeSourceRead]
    subscriptions: list[NoticeSubscriptionRead]
    notices: list[NoticeRead]
