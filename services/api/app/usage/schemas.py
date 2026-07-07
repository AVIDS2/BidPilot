from enum import StrEnum

from pydantic import BaseModel


class ProviderSource(StrEnum):
    OFFICIAL = "official"
    BYOK = "byok"
    STUB = "stub"


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
    trial_window_start: str
