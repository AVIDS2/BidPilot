from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ContentLifecycle = Literal["draft", "published", "archived"]
ContentReviewStatus = Literal["draft", "approved", "rejected"]


class ContentLibraryEntryCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content_type: str = Field(default="answer", min_length=1, max_length=50)
    category: str | None = Field(default=None, max_length=100)
    tags_json: list[str] = Field(default_factory=list, max_length=30)
    content_markdown: str = Field(min_length=1, max_length=200_000)
    source_json: dict | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    supersedes_entry_id: str | None = None


class ContentLibraryVersionCreate(BaseModel):
    content_markdown: str = Field(min_length=1, max_length=200_000)
    source_json: dict | None = None


class ContentLibraryPublish(BaseModel):
    effective_from: datetime | None = None
    effective_until: datetime | None = None


class ContentLibraryUsageCreate(BaseModel):
    project_id: str
    content_version_id: str | None = None
    deliverable_section_id: str | None = None
    usage_purpose: str = Field(default="reference", min_length=1, max_length=50)


class ContentLibraryVersionRead(BaseModel):
    id: str
    entry_id: str
    version_number: int
    content_markdown: str
    content_hash: str
    source_json: dict | None
    created_by_user_id: str | None
    created_at: datetime | None


class ContentLibraryUsageRead(BaseModel):
    id: str
    entry_id: str
    content_version_id: str
    project_id: str
    deliverable_section_id: str | None
    usage_purpose: str
    used_by_user_id: str | None
    created_at: datetime | None


class ContentLibraryEntryRead(BaseModel):
    id: str
    org_id: str
    title: str
    content_type: str
    category: str | None
    tags_json: list
    lifecycle_status: ContentLifecycle
    review_status: ContentReviewStatus
    owner_user_id: str | None
    effective_from: datetime | None
    effective_until: datetime | None
    supersedes_entry_id: str | None
    created_at: datetime | None
    updated_at: datetime | None
    latest_version: ContentLibraryVersionRead | None = None
    versions: list[ContentLibraryVersionRead] = Field(default_factory=list)
