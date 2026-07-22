from typing import Literal

from pydantic import BaseModel


class OrganizationEntitlementRead(BaseModel):
    org_id: str
    plan: str
    subscription_status: str
    source: Literal["organization", "legacy", "starter"]
    seat_limit: int
    active_member_count: int
    available_seats: int
    seat_overage_count: int
    capacity_enforced: bool
    project_limit: int
    monthly_workflow_limit: int
    monthly_assistant_limit: int
    monthly_indexing_limit: int
    is_billing_owner: bool
