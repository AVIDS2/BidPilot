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
    trial_window_start: str
