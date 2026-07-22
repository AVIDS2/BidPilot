from pydantic import BaseModel

from app.usage.schemas import ModelUsageSourceRead


class BillingSummaryRead(BaseModel):
    plan: str
    status: str
    stripe_customer_id: str | None = None
    entitlement_source: str = "starter"
    seat_limit: int = 1
    is_billing_owner: bool = False
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
