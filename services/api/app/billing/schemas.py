from pydantic import BaseModel


class BillingSummaryRead(BaseModel):
    plan: str
    status: str
    stripe_customer_id: str | None = None
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
