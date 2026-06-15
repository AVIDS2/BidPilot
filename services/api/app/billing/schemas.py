from pydantic import BaseModel


class BillingSummaryRead(BaseModel):
    plan: str
    status: str
    stripe_customer_id: str | None = None
    monthly_workflow_limit: int
    monthly_workflow_used: int
    monthly_workflow_remaining: int | None
    trial_window_start: str
