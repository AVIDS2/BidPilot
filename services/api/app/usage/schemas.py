from enum import StrEnum

from pydantic import BaseModel
from pydantic import Field


class ProviderSource(StrEnum):
    OFFICIAL = "official"
    BYOK = "byok"
    STUB = "stub"


class ModelUsageSourceRead(BaseModel):
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    total_tokens: int
    reserved_tokens: int
    token_limit: int | None
    remaining_tokens: int | None
    cost_available: bool = False


class UsageQuotaRead(BaseModel):
    plan: str
    monthly_workflow_limit: int
    monthly_workflow_used: int
    monthly_workflow_remaining: int | None
    monthly_assistant_limit: int
    monthly_assistant_used: int
    monthly_assistant_remaining: int | None
    monthly_indexing_limit: int
    monthly_indexing_used: int
    monthly_indexing_remaining: int | None
    official_model_usage: ModelUsageSourceRead
    byok_model_usage: ModelUsageSourceRead
    trial_window_start: str


class OrganizationUsageBudgetRead(BaseModel):
    official_monthly_token_limit: int | None
    byok_monthly_token_limit: int | None
    official_platform_monthly_token_ceiling: int | None
    effective_official_monthly_token_limit: int | None
    can_manage: bool


class OrganizationUsageBudgetUpdate(BaseModel):
    official_monthly_token_limit: int | None = Field(default=None, ge=0)
    byok_monthly_token_limit: int | None = Field(default=None, ge=0)
